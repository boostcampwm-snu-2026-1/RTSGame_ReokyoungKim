function gadget:GetInfo()
    return {
        name    = "Verify Spawn Unit",
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
local expectedSpawns = {}
local initialUnitCounts = {}

function gadget:Initialize()
    if not config then
        Spring.Echo("[FEEDBACK] No verify config available for spawn_unit")
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
            if not expectedSpawns[teamID] then
                expectedSpawns[teamID] = {}
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
                    for _, unitData in ipairs(wave.units) do
                        if not expectedSpawns[teamID][unitData.unitName] then
                            expectedSpawns[teamID][unitData.unitName] = {
                                count = 0,
                                triggerTime = triggerTime
                            }
                            initialUnitCounts[teamID][unitData.unitName] = getTeamUnitCount(teamID, unitData.unitName)
                        end
                        expectedSpawns[teamID][unitData.unitName].count = expectedSpawns[teamID][unitData.unitName].count + 1
                    end
                end
            end
        end
    end

    if next(expectedSpawns) == nil then
        Spring.Echo("[FEEDBACK] No time-based spawn waves found in config")
        return false
    end

    return true
end

local function checkSpawns()
    local failedSpawns = {}

    for teamID, units in pairs(expectedSpawns) do
        for unitName, spawnInfo in pairs(units) do
            local initialCount = initialUnitCounts[teamID][unitName] or 0
            local currentCount = getTeamUnitCount(teamID, unitName)
            local spawnedCount = currentCount - initialCount

            if spawnedCount < spawnInfo.count then
                table.insert(failedSpawns, {
                    teamID = teamID,
                    unitName = unitName,
                    expected = spawnInfo.count,
                    actual = spawnedCount
                })
            end
        end
    end

    return failedSpawns
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
        for teamID, units in pairs(expectedSpawns) do
            for unitName, spawnInfo in pairs(units) do
                if spawnInfo.triggerTime > maxTriggerTime then
                    maxTriggerTime = spawnInfo.triggerTime
                end
            end
        end

        local waitFrames = (maxTriggerTime + 3) * 30
        if frame - testStartFrame > waitFrames then
            local failedSpawns = checkSpawns()

            if #failedSpawns > 0 then
                for _, failure in ipairs(failedSpawns) do
                    Spring.Echo(string.format("[FEEDBACK] Spawn failed - Team %d: %s expected %d, spawned %d",
                        failure.teamID, failure.unitName, failure.expected, failure.actual))
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
