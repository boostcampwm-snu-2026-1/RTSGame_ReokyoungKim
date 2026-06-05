function gadget:GetInfo()
    return {
        name    = "Verify Restrict Target",
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
local attackerUnits = {}
local restrictedTargets = {}
local validTargets = {}

function gadget:Initialize()
    if not config then
        Spring.Echo("[FEEDBACK] No verify config available for restrict_target")
        testState = "failed"
        return
    end
end

function gadget:GameStart()
    testStartFrame = Spring.GetGameFrame()
    testState = "setup"
end

local function setupTest()
    for teamIDStr, restrictedNames in pairs(config) do
        local teamID = tonumber(teamIDStr)
        if teamID then
            local restrictedLookup = {}
            for _, name in ipairs(restrictedNames) do
                restrictedLookup[name] = true
            end

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
                                restrictedLookup = restrictedLookup
                            }
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
                            if restrictedLookup[unitDef.name] then
                                restrictedTargets[unitID] = {
                                    teamID = unitTeam,
                                    unitName = unitDef.name
                                }
                            else
                                validTargets[unitID] = {
                                    teamID = unitTeam,
                                    unitName = unitDef.name
                                }
                            end
                        end
                    end
                end
            end
        end
    end

    if next(attackerUnits) == nil then
        Spring.Echo("[FEEDBACK] No attacker units found for restrict_target test")
        return false
    end

    if next(restrictedTargets) == nil then
        Spring.Echo("[FEEDBACK] No restricted targets found for restrict_target test")
        return false
    end

    return true
end

local function moveAttackersAndIssueCommand()
    local restrictedID = next(restrictedTargets)
    if not restrictedID then return end

    local tx, ty, tz = Spring.GetUnitPosition(restrictedID)
    if not tx then return end

    for unitID, unitInfo in pairs(attackerUnits) do
        local offsetX = (math.random() - 0.5) * 200
        local offsetZ = (math.random() - 0.5) * 200
        Spring.SetUnitPosition(unitID, tx + offsetX, tz + offsetZ, true)
        Spring.GiveOrderToUnit(unitID, CMD.ATTACK, {restrictedID}, {})
    end
end

local function checkTargeting()
    local failedUnits = {}

    for unitID, unitInfo in pairs(attackerUnits) do
        local cmdQueue = Spring.GetUnitCommands(unitID, 1)

        if cmdQueue and #cmdQueue > 0 then
            local cmd = cmdQueue[1]
            if cmd.id == CMD.ATTACK and cmd.params and #cmd.params == 1 then
                local targetID = cmd.params[1]
                if targetID and restrictedTargets[targetID] then
                    table.insert(failedUnits, {
                        unitID = unitID,
                        unitName = unitInfo.unitName,
                        teamID = unitInfo.teamID,
                        targetID = targetID,
                        targetName = restrictedTargets[targetID].unitName
                    })
                end
            end
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
            testState = "commanding"
            moveAttackersAndIssueCommand()
            testStartFrame = frame
        else
            testState = "failed"
        end

    elseif testState == "commanding" then
        if frame - testStartFrame > 60 then
            local failedUnits = checkTargeting()

            if #failedUnits > 0 then
                for _, failure in ipairs(failedUnits) do
                    Spring.Echo(string.format("[FEEDBACK] Restrict target failed - Unit %d (%s, Team %d) still targeting restricted %s",
                        failure.unitID, failure.unitName, failure.teamID, failure.targetName))
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
    restrictedTargets[unitID] = nil
    validTargets[unitID] = nil
end
