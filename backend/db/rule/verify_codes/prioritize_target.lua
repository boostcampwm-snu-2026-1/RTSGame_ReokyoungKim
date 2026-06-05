function gadget:GetInfo()
    return {
        name    = "Verify Prioritize Target",
        layer   = 1,
        enabled = false
    }
end

if not gadgetHandler:IsSyncedCode() then
    return
end

local config = nil

local testState = "waiting"
local testStartFrame = nil
local moveWaitDuration = 90
local attackWaitDuration = 60
local attackerUnits = {}
local priorityTargets = {}

function gadget:Initialize()
    if not config then
        Spring.Echo("[FEEDBACK] No verify config available for prioritize_target")
        testState = "failed"
        return
    end
end

function gadget:GameStart()
    testStartFrame = Spring.GetGameFrame()
    testState = "setup"
end

local function setupTest()
    for teamIDStr, teamConfig in pairs(config) do
        local teamID = tonumber(teamIDStr)
        if teamID then
            local teamUnits = Spring.GetTeamUnits(teamID)
            if teamUnits then
                for _, unitID in ipairs(teamUnits) do
                    local unitDefID = Spring.GetUnitDefID(unitID)
                    if unitDefID then
                        local unitDef = UnitDefs[unitDefID]
                        if unitDef and unitDef.canAttack and not unitDef.isBuilder then
                            attackerUnits[unitID] = {
                                teamID = teamID,
                                unitName = unitDef.name,
                                priorityTargets = {}
                            }
                            for _, targetName in ipairs(teamConfig.targets) do
                                attackerUnits[unitID].priorityTargets[targetName] = true
                            end
                        end
                    end
                end
            end

            local allUnits = Spring.GetAllUnits()
            for _, unitID in ipairs(allUnits) do
                local unitTeam = Spring.GetUnitTeam(unitID)
                if unitTeam and unitTeam ~= teamID then
                    local unitDefID = Spring.GetUnitDefID(unitID)
                    if unitDefID then
                        local unitDef = UnitDefs[unitDefID]
                        if unitDef then
                            for _, targetName in ipairs(teamConfig.targets) do
                                if unitDef.name == targetName then
                                    priorityTargets[unitID] = {
                                        teamID = unitTeam,
                                        unitName = unitDef.name
                                    }
                                    break
                                end
                            end
                        end
                    end
                end
            end
        end
    end

    if next(attackerUnits) == nil then
        Spring.Echo("[FEEDBACK] No attacker units found for prioritize_target test")
        return false
    end

    if next(priorityTargets) == nil then
        Spring.Echo("[FEEDBACK] No priority targets found for prioritize_target test")
        return false
    end

    return true
end

local function moveAttackersToTargets()
    local targetID = next(priorityTargets)
    if not targetID then return end

    local tx, ty, tz = Spring.GetUnitPosition(targetID)
    if not tx then return end

    for unitID, unitInfo in pairs(attackerUnits) do
        local offsetX = (math.random() - 0.5) * 200
        local offsetZ = (math.random() - 0.5) * 200
        local moveX = tx + offsetX
        local moveZ = tz + offsetZ

        Spring.SetUnitPosition(unitID, moveX, tz + offsetZ, true)
    end
end

local function checkTargeting()
    local failedUnits = {}

    for unitID, unitInfo in pairs(attackerUnits) do
        local cmdQueue = Spring.GetUnitCommands(unitID, 1)
        local isAttackingPriority = false

        if cmdQueue and #cmdQueue > 0 then
            local cmd = cmdQueue[1]
            if cmd.id == CMD.ATTACK and cmd.params and #cmd.params == 1 then
                local targetID = cmd.params[1]
                if targetID then
                    local targetDefID = Spring.GetUnitDefID(targetID)
                    if targetDefID then
                        local targetDef = UnitDefs[targetDefID]
                        if targetDef and unitInfo.priorityTargets[targetDef.name] then
                            isAttackingPriority = true
                        end
                    end
                end
            end
        end

        if not isAttackingPriority then
            local currentTargetName = "none"
            if cmdQueue and #cmdQueue > 0 then
                local cmd = cmdQueue[1]
                if cmd.id == CMD.ATTACK and cmd.params and #cmd.params == 1 then
                    local targetID = cmd.params[1]
                    if targetID then
                        local targetDefID = Spring.GetUnitDefID(targetID)
                        if targetDefID then
                            local targetDef = UnitDefs[targetDefID]
                            if targetDef then
                                currentTargetName = targetDef.name
                            end
                        end
                    end
                end
            end

            table.insert(failedUnits, {
                unitID = unitID,
                unitName = unitInfo.unitName,
                teamID = unitInfo.teamID,
                currentTarget = currentTargetName
            })
        end
    end

    return failedUnits
end

function gadget:GameFrame(frame)
    if testState == "waiting" then
        if testStartFrame and frame - testStartFrame > 30 then
            testState = "setup"
        end

    elseif testState == "setup" then
        if setupTest() then
            testState = "moving"
            moveAttackersToTargets()
            testStartFrame = frame
        else
            testState = "failed"
        end

    elseif testState == "moving" then
        if frame - testStartFrame > moveWaitDuration then
            testState = "checking"
            testStartFrame = frame
        end

    elseif testState == "checking" then
        if frame - testStartFrame > attackWaitDuration then
            local failedUnits = checkTargeting()

            if #failedUnits > 0 then
                for _, failure in ipairs(failedUnits) do
                    Spring.Echo(string.format("[FEEDBACK] Priority targeting failed - Unit %d (%s, Team %d) attacking '%s' instead of priority target",
                        failure.unitID, failure.unitName, failure.teamID, failure.currentTarget))
                end
                testState = "failed"
            else
                testState = "complete"
            end
        end

    elseif testState == "complete" then
        testState = "done"

    elseif testState == "failed" then
        testState = "done"

    elseif testState == "done" then
        Spring.SendCommands("quitforce")
    end
end

function gadget:UnitDestroyed(unitID, unitDefID, unitTeam)
    attackerUnits[unitID] = nil
    priorityTargets[unitID] = nil
end
