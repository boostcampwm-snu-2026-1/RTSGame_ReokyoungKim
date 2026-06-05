function gadget:GetInfo()
    return {
        name    = "Prioritize Target",
        layer   = 0,
        enabled = false
    }
end

if not gadgetHandler:IsSyncedCode() then
    return
end

local config = nil

local prioritizeTargetLookup = {}
local teamRanges = {}

function gadget:Initialize()
    Spring.Echo("[GADGET] Prioritize Target loaded")
    for teamID, teamConfig in pairs(config) do
        prioritizeTargetLookup[teamID] = {}
        local range = teamConfig.range or 500
        teamRanges[teamID] = range
        for _, unitName in ipairs(teamConfig.targets) do
            prioritizeTargetLookup[teamID][unitName] = true
        end
        Spring.Echo(string.format("[GADGET] Team %s prioritizes: %s (range: %d)", teamID, table.concat(teamConfig.targets, ", "), range))
    end
end

function gadget:GameFrame(frame)
    if frame % 30 ~= 0 then return end

    for teamIDStr, priorityUnits in pairs(prioritizeTargetLookup) do
        local teamID = tonumber(teamIDStr)
        if teamID then
            local teamUnits = Spring.GetTeamUnits(teamID)
            if teamUnits then
                for _, unitID in ipairs(teamUnits) do
                    local unitDefID = Spring.GetUnitDefID(unitID)
                    if unitDefID then
                        local unitDef = UnitDefs[unitDefID]
                        if unitDef and unitDef.canAttack and not unitDef.isBuilder then
                            local ux, uy, uz = Spring.GetUnitPosition(unitID)
                            if ux then
                                local nearestTarget = nil
                                local priorityRange = teamRanges[teamIDStr] or 500
                                local nearestDist = priorityRange * priorityRange

                                local allUnits = Spring.GetAllUnits()
                                for _, targetID in ipairs(allUnits) do
                                    local targetTeam = Spring.GetUnitTeam(targetID)
                                    if targetTeam and targetTeam ~= teamID then
                                        local targetDefID = Spring.GetUnitDefID(targetID)
                                        if targetDefID then
                                            local targetDef = UnitDefs[targetDefID]
                                            if targetDef and priorityUnits[targetDef.name] then
                                                local tx, ty, tz = Spring.GetUnitPosition(targetID)
                                                if tx then
                                                    local dx = ux - tx
                                                    local dz = uz - tz
                                                    local distSq = dx * dx + dz * dz
                                                    if distSq < nearestDist then
                                                        nearestDist = distSq
                                                        nearestTarget = targetID
                                                    end
                                                end
                                            end
                                        end
                                    end
                                end

                                if nearestTarget then
                                    Spring.GiveOrderToUnit(unitID, CMD.ATTACK, {nearestTarget}, {})
                                end
                            end
                        end
                    end
                end
            end
        end
    end
end
