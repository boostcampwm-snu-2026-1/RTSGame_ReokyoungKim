function gadget:GetInfo()
    return {
        name    = "Auto Construct",
        layer   = 0,
        enabled = false
    }
end

if not gadgetHandler:IsSyncedCode() then
    return
end

local config = nil
local autoConstructLookup = {}

function gadget:Initialize()
    Spring.Echo("[GADGET] Auto Construct loaded")
    for teamID, units in pairs(config) do
        autoConstructLookup[teamID] = {}
        for _, unitName in ipairs(units) do
            autoConstructLookup[teamID][unitName] = true
        end
        Spring.Echo(string.format("[GADGET] Team %s auto-constructs: %s", teamID, table.concat(units, ", ")))
    end
end

function gadget:GameFrame(frame)
    if frame % 10 ~= 0 then return end

    for teamIDStr, lookup in pairs(autoConstructLookup) do
        local teamID = tonumber(teamIDStr)
        if teamID then
            local teamUnits = Spring.GetTeamUnits(teamID)
            if teamUnits then
                for _, unitID in ipairs(teamUnits) do
                    local unitDefID = Spring.GetUnitDefID(unitID)
                    if unitDefID then
                        local unitDef = UnitDefs[unitDefID]
                        if unitDef and lookup[unitDef.name] then
                            local health, maxHealth, _, _, buildProgress = Spring.GetUnitHealth(unitID)
                            if buildProgress and buildProgress < 1 then
                                Spring.SetUnitHealth(unitID, {health = maxHealth, build = 1})
                                Spring.Echo(string.format("[GADGET] Auto-completed %s (ID:%d) for team %d", unitDef.name, unitID, teamID))
                            end
                        end
                    end
                end
            end
        end
    end
end