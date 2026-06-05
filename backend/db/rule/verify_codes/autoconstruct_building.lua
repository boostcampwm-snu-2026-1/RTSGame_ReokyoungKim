function gadget:GetInfo()
    return {
        name    = "Verify Auto Construct",
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
local testBuildings = {}
local spawnedBuildingIDs = {}

function gadget:Initialize()
    if not config then
        Spring.Echo("[FEEDBACK] No verify config available for autoconstruct_building")
        testState = "failed"
        return
    end
end

function gadget:GameStart()
    testStartFrame = Spring.GetGameFrame()
    testState = "setup"
end

local function setupTest()
    for teamIDStr, buildings in pairs(config) do
        local teamID = tonumber(teamIDStr)
        if teamID then
            testBuildings[teamID] = {}
            for _, buildingName in ipairs(buildings) do
                testBuildings[teamID][buildingName] = true
            end
        end
    end

    if next(testBuildings) == nil then
        Spring.Echo("[FEEDBACK] No buildings configured for autoconstruct test")
        return false
    end

    return true
end

local function spawnTestBuildings()
    for teamID, buildings in pairs(testBuildings) do
        for buildingName, _ in pairs(buildings) do
            local unitDef = UnitDefNames[buildingName]
            if unitDef then
                local x = 1000 + math.random(0, 500)
                local z = 1000 + math.random(0, 500)
                local y = Spring.GetGroundHeight(x, z)

                local unitID = Spring.CreateUnit(buildingName, x, y, z, 0, teamID, true)
                if unitID then
                    Spring.SetUnitHealth(unitID, {build = 0.1})
                    if not spawnedBuildingIDs[teamID] then
                        spawnedBuildingIDs[teamID] = {}
                    end
                    table.insert(spawnedBuildingIDs[teamID], {
                        unitID = unitID,
                        unitName = buildingName
                    })
                end
            end
        end
    end
end

local function checkAutoConstruct()
    local failedBuildings = {}

    for teamID, buildings in pairs(spawnedBuildingIDs) do
        for _, buildingInfo in ipairs(buildings) do
            local unitID = buildingInfo.unitID
            local health, maxHealth, _, _, buildProgress = Spring.GetUnitHealth(unitID)

            if buildProgress and buildProgress < 1 then
                table.insert(failedBuildings, {
                    teamID = teamID,
                    unitID = unitID,
                    unitName = buildingInfo.unitName,
                    buildProgress = buildProgress
                })
            end
        end
    end

    return failedBuildings
end

function gadget:GameFrame(frame)
    if testState == "waiting" then
        if testStartFrame and frame - testStartFrame > 30 then
            testState = "setup"
        end

    elseif testState == "setup" then
        if setupTest() then
            testState = "spawning"
        else
            testState = "failed"
        end

    elseif testState == "spawning" then
        spawnTestBuildings()
        testStartFrame = frame
        testState = "checking"

    elseif testState == "checking" then
        if frame - testStartFrame > 30 then
            local failedBuildings = checkAutoConstruct()

            if #failedBuildings > 0 then
                for _, failure in ipairs(failedBuildings) do
                    Spring.Echo(string.format("[FEEDBACK] Auto-construct failed - Team %d: %s (ID %d) still at %.0f%% build progress",
                        failure.teamID, failure.unitName, failure.unitID, failure.buildProgress * 100))
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
