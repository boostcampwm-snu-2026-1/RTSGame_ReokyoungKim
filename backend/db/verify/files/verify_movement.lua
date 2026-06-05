function gadget:GetInfo()
    return {
        name    = "Verify Movement",
        layer   = 0,
        enabled = false
    }
end

if not gadgetHandler:IsSyncedCode() then
    return
end

local config = nil

local expectedUnits = {}
local verificationState = "waiting"
local verificationResults = {}
local unitsToTest = {}
local unitOriginalPositions = {}
local movementTestStartFrame = nil
local movementTestDuration = 90
local verificationStartFrame = nil

local function loadGameConfig()
    local unitPlacement = config.unit_placement
    if not unitPlacement then
        Spring.Echo("[FEEDBACK] No unit_placement in config")
        return false
    end

    for teamID, units in pairs(unitPlacement) do
        teamID = tonumber(teamID)
        if not expectedUnits[teamID] then
            expectedUnits[teamID] = {}
        end

        for _, unitData in ipairs(units) do
            local unitName = unitData[1]
            expectedUnits[teamID][unitName] = (expectedUnits[teamID][unitName] or 0) + 1
        end
    end

    return true
end

function gadget:Initialize()
    if not config then
        Spring.Echo("[FEEDBACK] No config available")
        verificationState = "failed"
        return
    end

    if loadGameConfig() then
        verificationState = "ready"
    else
        verificationState = "failed"
    end
end

function gadget:GameStart()
    verificationStartFrame = Spring.GetGameFrame()
    verificationState = "waiting"
end

function gadget:AllowCommand(unitID, unitDefID, teamID, cmdID, cmdParams, cmdOpts)
    if unitsToTest[unitID] and unitsToTest[unitID].testingCommand then
        return true
    end
    return false
end

local function verifyUnitPlacement()
    local actualUnits = {}
    local allUnits = Spring.GetAllUnits()

    for _, unitID in ipairs(allUnits) do
        local teamID = Spring.GetUnitTeam(unitID)
        local unitDefID = Spring.GetUnitDefID(unitID)

        if unitDefID then
            local unitDef = UnitDefs[unitDefID]
            local unitName = unitDef.name

            if not actualUnits[teamID] then
                actualUnits[teamID] = {}
            end

            actualUnits[teamID][unitName] = (actualUnits[teamID][unitName] or 0) + 1
        end
    end

    local placementValid = true
    local mismatchMessages = {}

    for teamID, expectedTeamUnits in pairs(expectedUnits) do
        for unitName, expectedCount in pairs(expectedTeamUnits) do
            local actualCount = (actualUnits[teamID] and actualUnits[teamID][unitName]) or 0

            if actualCount ~= expectedCount then
                placementValid = false
                table.insert(mismatchMessages, string.format("Team %d: %s expected %d, got %d", teamID, unitName, expectedCount, actualCount))
            end
        end
    end

    for teamID, actualTeamUnits in pairs(actualUnits) do
        for unitName, actualCount in pairs(actualTeamUnits) do
            if not (expectedUnits[teamID] and expectedUnits[teamID][unitName]) then
                table.insert(mismatchMessages, string.format("Team %d: Unexpected unit %s x%d", teamID, unitName, actualCount))
            end
        end
    end

    if placementValid then
        verificationResults.placement = "PASSED"
        return true
    else
        for _, msg in ipairs(mismatchMessages) do
            Spring.Echo("[FEEDBACK] Placement mismatch - " .. msg)
        end
        verificationResults.placement = "FAILED"
        return false
    end
end

local function startMovementTest()
    local allUnits = Spring.GetAllUnits()

    for _, unitID in ipairs(allUnits) do
        local unitDefID = Spring.GetUnitDefID(unitID)

        if unitDefID then
            local unitDef = UnitDefs[unitDefID]

            if unitDef.speed and unitDef.speed > 0 then
                local x, y, z = Spring.GetUnitPosition(unitID)

                if x then
                    unitOriginalPositions[unitID] = {x = x, y = y, z = z}

                    local angle = math.random() * 2 * math.pi
                    local moveDistance = 50
                    local targetX = x + math.cos(angle) * moveDistance
                    local targetZ = z + math.sin(angle) * moveDistance

                    unitsToTest[unitID] = {
                        testingCommand = true,
                        unitName = unitDef.name,
                        teamID = Spring.GetUnitTeam(unitID)
                    }

                    Spring.GiveOrderToUnit(unitID, CMD.MOVE, {targetX, y, targetZ}, {})
                end
            end
        end
    end

    movementTestStartFrame = Spring.GetGameFrame()
end

local function checkMovementResults()
    local movedCount = 0
    local stuckCount = 0
    local totalTested = 0

    for unitID, originalPos in pairs(unitOriginalPositions) do
        totalTested = totalTested + 1
        local x, y, z = Spring.GetUnitPosition(unitID)

        if x then
            local distance = math.sqrt((x - originalPos.x)^2 + (z - originalPos.z)^2)
            local unitInfo = unitsToTest[unitID]

            if distance > 5 then
                movedCount = movedCount + 1
            else
                stuckCount = stuckCount + 1

                local unitDefID = Spring.GetUnitDefID(unitID)
                local unitDef = UnitDefs[unitDefID]
                local groundHeight = Spring.GetGroundHeight(x, z)
                local waterLevel = 0
                local isOnWater = (groundHeight < waterLevel)

                local moveType = "unknown"
                local minWaterDepth = unitDef.minWaterDepth or 0
                local isWaterUnit = minWaterDepth > 0
                local isLandUnit = minWaterDepth < 0

                if isWaterUnit then
                    moveType = "Water"
                elseif isLandUnit then
                    moveType = "Land"
                else
                    moveType = "Amphibious"
                end

                if (isWaterUnit and not isOnWater) or (isLandUnit and isOnWater) then
                    Spring.Echo(string.format("[FEEDBACK] Terrain mismatch - Unit %d (%s, Team %d) is %s unit but placed on %s",
                        unitID, unitInfo.unitName, unitInfo.teamID, moveType, isOnWater and "water" or "land"))
                else
                    Spring.Echo(string.format("[FEEDBACK] Unit stuck - Unit %d (%s, Team %d) blocked by terrain, moved only %.1f units",
                        unitID, unitInfo.unitName, unitInfo.teamID, distance))
                end
            end
        end
    end

    if stuckCount == 0 then
        verificationResults.movement = "PASSED"
        return true
    else
        verificationResults.movement = "FAILED"
        return false
    end
end

function gadget:GameFrame(frame)
    if verificationState == "waiting" then
        if verificationStartFrame and frame - verificationStartFrame > 60 then
            verificationState = "verifying_placement"
        end

    elseif verificationState == "verifying_placement" then
        if verifyUnitPlacement() then
            verificationState = "starting_movement_test"
        else
            verificationState = "failed"
        end

    elseif verificationState == "starting_movement_test" then
        startMovementTest()
        verificationState = "verifying_movement"

    elseif verificationState == "verifying_movement" then
        if movementTestStartFrame and frame - movementTestStartFrame > movementTestDuration then
            if checkMovementResults() then
                verificationState = "complete"
            else
                verificationState = "failed"
            end
        end

    elseif verificationState == "complete" then
        verificationState = "done"

    elseif verificationState == "failed" then
        Spring.Echo("[FEEDBACK] Verification failed - Placement: " .. (verificationResults.placement or "NOT TESTED") .. ", Movement: " .. (verificationResults.movement or "NOT TESTED"))
        verificationState = "done"

    elseif verificationState == "done" then
        Spring.SendCommands("quitforce")
    end
end

function gadget:UnitDestroyed(unitID, unitDefID, unitTeam)
    unitsToTest[unitID] = nil
    unitOriginalPositions[unitID] = nil
end
