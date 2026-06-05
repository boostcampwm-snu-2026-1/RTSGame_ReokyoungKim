function gadget:GetInfo()
    return {
        name    = "Control Despawn",
        layer   = 0,
        enabled = false
    }
end

if not gadgetHandler:IsSyncedCode() then
    return
end

local despawnWaves = nil
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
    Spring.Echo("[GADGET] Control Despawn loaded")

    if despawnWaves then
        for teamID, waves in pairs(despawnWaves) do
            for waveIndex, wave in ipairs(waves) do
                local despawnInfo = {}
                for _, d in ipairs(wave.despawn) do
                    table.insert(despawnInfo, d.unitName .. "x" .. d.count)
                end
                Spring.Echo(string.format("[GADGET] Registered despawn wave for team %d: %s",
                    teamID, table.concat(despawnInfo, ", ")))
            end
        end
    else
        Spring.Echo("[GADGET] No despawn waves configured")
    end
end

function gadget:GameFrame(frame)
    if not despawnWaves then
        return
    end

    local currentTime = frame / 30

    for teamID, waves in pairs(despawnWaves) do
        for waveIndex, wave in ipairs(waves) do
            local waveKey = teamID .. "_" .. waveIndex

            if not processedWaves[waveKey] and checkCondition(wave.condition, currentTime) then
                Spring.Echo(string.format("[GADGET] Despawn wave %d triggered for team %d at time %.1fs",
                    waveIndex, teamID, currentTime))

                for _, despawnData in ipairs(wave.despawn) do
                    local unitDefID = UnitDefNames[despawnData.unitName]
                    if unitDefID then
                        local units = Spring.GetTeamUnitsByDefs(teamID, unitDefID.id)
                        if units then
                            local removeCount = math.min(despawnData.count, #units)
                            for i = 1, removeCount do
                                local unitID = units[i]
                                Spring.DestroyUnit(unitID, false, true)
                                Spring.Echo(string.format("[GADGET] Despawned %s (ID:%d) from team %d",
                                    despawnData.unitName, unitID, teamID))
                            end
                        end
                    else
                        Spring.Echo(string.format("[GADGET ERROR] Unknown unit type: %s", despawnData.unitName))
                    end
                end

                processedWaves[waveKey] = true
            end
        end
    end
end