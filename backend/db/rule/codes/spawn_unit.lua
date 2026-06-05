function gadget:GetInfo()
    return {
        name    = "Control Spawn",
        layer   = 0,
        enabled = false
    }
end

if not gadgetHandler:IsSyncedCode() then
    return
end

local config = nil
local processedWaves = {}

local function getTeamUnitCount(teamID, unitCode)
    if unitCode == "all" then
        local allUnits = Spring.GetTeamUnits(teamID)
        return allUnits and #allUnits or 0
    else
        local unitDefID = UnitDefNames[unitCode]
        if unitDefID then
            local units = Spring.GetTeamUnitsByDefs(teamID, unitDefID.id)
            return units and #units or 0
        end
        return 0
    end
end

local function evaluateComparison(actual, op, required)
    if op == "==" then
        return actual == required
    elseif op == "!=" then
        return actual ~= required
    elseif op == ">=" then
        return actual >= required
    elseif op == "<=" then
        return actual <= required
    elseif op == ">" then
        return actual > required
    elseif op == "<" then
        return actual < required
    end
    return false
end

local function findValidSpawnPosition(unitDefID, x, z, maxRadius, step)
    maxRadius = maxRadius or 500
    step = step or 50

    local y = Spring.GetGroundHeight(x, z)
    if Spring.TestMoveOrder(unitDefID, x, y, z) then
        return x, z
    end

    local dx, dz = step, 0
    local segmentLength = 1
    local segmentPassed = 0
    local dirChanges = 0

    local currentX, currentZ = x, z

    while math.abs(currentX - x) <= maxRadius and math.abs(currentZ - z) <= maxRadius do
        currentX = currentX + dx
        currentZ = currentZ + dz
        segmentPassed = segmentPassed + 1

        local testY = Spring.GetGroundHeight(currentX, currentZ)
        if Spring.TestMoveOrder(unitDefID, currentX, testY, currentZ) then
            return currentX, currentZ
        end

        if segmentPassed >= segmentLength then
            segmentPassed = 0
            dirChanges = dirChanges + 1

            if dx > 0 then
                dx, dz = 0, step
            elseif dz > 0 then
                dx, dz = -step, 0
            elseif dx < 0 then
                dx, dz = 0, -step
            else
                dx, dz = step, 0
            end

            if dirChanges % 2 == 0 then
                segmentLength = segmentLength + 1
            end
        end
    end

    return x, z
end

local function checkCondition(condition, currentTime)
    local operator = condition.operator
    local checks = condition.checks

    local results = {}
    for _, check in ipairs(checks) do
        local passed = false

        if check.type == "time" then
            local op = check.op or ">="
            passed = evaluateComparison(currentTime, op, check.value)
        elseif check.type == "unit_count" then
            local count = getTeamUnitCount(check.teamID, check.unitCode)
            local op = check.op or ">="
            passed = evaluateComparison(count, op, check.value)
        end

        table.insert(results, passed)
    end

    if operator == "and" then
        for _, result in ipairs(results) do
            if not result then return false end
        end
        return true
    elseif operator == "or" then
        for _, result in ipairs(results) do
            if result then return true end
        end
        return false
    end

    return false
end

function gadget:Initialize()
    Spring.Echo("[GADGET] Gadget loaded (Initialize)")

    if config then
        for teamID, waves in pairs(config) do
            for waveIndex, wave in ipairs(waves) do
                Spring.Echo(string.format("[GADGET] Registered wave for team %d with %d units",
                    teamID, #wave.units))
            end
        end
    else
        Spring.Echo("[GADGET] No spawn waves configured")
    end
end

function gadget:GameStart()
    Spring.Echo("[GADGET] Tower Defense GameStart called")
end

function gadget:GameFrame(frame)
    if not config then
        return
    end

    local currentTime = frame / 30

    for teamID, waves in pairs(config) do
        for waveIndex, wave in ipairs(waves) do
            local waveKey = teamID .. "_" .. waveIndex

            if not processedWaves[waveKey] and checkCondition(wave.condition, currentTime) then
                Spring.Echo(string.format("[GADGET] Spawning wave %d for team %d at time %.1fs",
                    waveIndex, teamID, currentTime))

                for _, unitData in ipairs(wave.units) do
                    local unitDef = UnitDefNames[unitData.unitName]
                    if unitDef then
                        local spawnX, spawnZ = findValidSpawnPosition(unitDef.id, unitData.x, unitData.z)
                        local y = Spring.GetGroundHeight(spawnX, spawnZ)
                        local unitID = Spring.CreateUnit(unitDef.id, spawnX, y, spawnZ, 0, teamID)

                        if unitID then
                            Spring.Echo(string.format("[GADGET] Spawned %s (ID:%d) for team %d at (%.1f, %.1f)",
                                unitData.unitName, unitID, teamID, spawnX, spawnZ))
                        else
                            Spring.Echo(string.format("[GADGET ERROR] Failed to spawn %s for team %d",
                                unitData.unitName, teamID))
                        end
                    else
                        Spring.Echo(string.format("[GADGET ERROR] Unknown unit type: %s", unitData.unitName))
                    end
                end

                processedWaves[waveKey] = true
            end
        end
    end
end