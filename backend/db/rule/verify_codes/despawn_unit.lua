function gadget:GetInfo()
    return {
        name    = "Verify Despawn Unit",
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
local expectedDespawns = {}
local initialUnitCounts = {}

function gadget:Initialize()
    if not config then
        Spring.Echo("[FEEDBACK] No verify config available for despawn_unit")
        testState = "failed"
        return
    end
end

function gadget:GameStart()
    testStartFrame = Spring.GetGameFrame()
    testState = "setup"
end

local function getTeamUnitCount(teamID, unitName)
    local unitDef = UnitDefNames[unitName]
    if unitDef then
        local units = Spring.GetTeamUnitsByDefs(teamID, unitDef.id)
        return units and #units or 0
    end
    return 0
end

local function setupTest()
    for teamIDStr, waves in pairs(config) do
        local teamID = tonumber(teamIDStr)
        if teamID then
            if not expectedDespawns[teamID] then
                expectedDespawns[teamID] = {}
                initialUnitCounts[teamID] = {}
            end

            for _, wave in ipairs(waves) do
                local triggerTime = nil
                for _, check in ipairs(wave.condition.checks) do
                    if check.type == "time" and check.op == ">=" then
                        triggerTime = check.value
                        break
                    end
                end

                if triggerTime then
                    for _, despawnData in ipairs(wave.despawn) do
                        if not expectedDespawns[teamID][despawnData.unitName] then
                            expectedDespawns[teamID][despawnData.unitName] = {
                                count = 0,
                                triggerTime = triggerTime
                            }
                            initialUnitCounts[teamID][despawnData.unitName] = getTeamUnitCount(teamID, despawnData.unitName)
                        end
                        expectedDespawns[teamID][despawnData.unitName].count = expectedDespawns[teamID][despawnData.unitName].count + despawnData.count
                    end
                end
            end
        end
    end

    if next(expectedDespawns) == nil then
        Spring.Echo("[FEEDBACK] No time-based despawn waves found in config")
        return false
    end

    return true
end

local function checkDespawns()
    local failedDespawns = {}

    for teamID, units in pairs(expectedDespawns) do
        for unitName, despawnInfo in pairs(units) do
            local initialCount = initialUnitCounts[teamID][unitName] or 0
            local currentCount = getTeamUnitCount(teamID, unitName)
            local despawnedCount = initialCount - currentCount

            local expectedDespawn = math.min(despawnInfo.count, initialCount)
            if despawnedCount < expectedDespawn then
                table.insert(failedDespawns, {
                    teamID = teamID,
                    unitName = unitName,
                    expected = expectedDespawn,
                    actual = despawnedCount,
                    initialCount = initialCount
                })
            end
        end
    end

    return failedDespawns
end

function gadget:GameFrame(frame)
    if testState == "waiting" then
        if testStartFrame and frame - testStartFrame > 30 then
            testState = "setup"
        end

    elseif testState == "setup" then
        if setupTest() then
            testState = "testing"
            testStartFrame = frame
        else
            testState = "failed"
        end

    elseif testState == "testing" then
        local maxTriggerTime = 0
        for teamID, units in pairs(expectedDespawns) do
            for unitName, despawnInfo in pairs(units) do
                if despawnInfo.triggerTime > maxTriggerTime then
                    maxTriggerTime = despawnInfo.triggerTime
                end
            end
        end

        local waitFrames = (maxTriggerTime + 3) * 30
        if frame - testStartFrame > waitFrames then
            local failedDespawns = checkDespawns()

            if #failedDespawns > 0 then
                for _, failure in ipairs(failedDespawns) do
                    Spring.Echo(string.format("[FEEDBACK] Despawn failed - Team %d: %s expected %d despawned (from %d), actual %d",
                        failure.teamID, failure.unitName, failure.expected, failure.initialCount, failure.actual))
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
