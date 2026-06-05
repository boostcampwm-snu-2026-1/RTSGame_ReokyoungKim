function gadget:GetInfo()
    return {
        name    = "Restrict Target",
        layer   = 0,
        enabled = false
    }
end

if not gadgetHandler:IsSyncedCode() then
    return
end

local config = nil
local restrictedTargetLookup = {}

function gadget:Initialize()
    for teamID, units in pairs(config) do
        restrictedTargetLookup[teamID] = {}
        for _, unitName in ipairs(units) do
            restrictedTargetLookup[teamID][unitName] = true
        end
    end
end

local function findNearestValidTarget(unitID, unitTeam, restricted)
    local ux, uy, uz = Spring.GetUnitPosition(unitID)
    if not ux then return nil end

    local unitDefID = Spring.GetUnitDefID(unitID)
    if not unitDefID then return nil end

    local unitDef = UnitDefs[unitDefID]
    if not unitDef or not unitDef.maxWeaponRange then return nil end

    local searchRange = unitDef.maxWeaponRange * 1.5
    local nearestTarget = nil
    local nearestDistSq = searchRange * searchRange

    local allUnits = Spring.GetAllUnits()
    for _, targetID in ipairs(allUnits) do
        local targetTeam = Spring.GetUnitTeam(targetID)
        if targetTeam and targetTeam ~= unitTeam and not Spring.AreTeamsAllied(unitTeam, targetTeam) then
            local targetDefID = Spring.GetUnitDefID(targetID)
            if targetDefID then
                local targetDef = UnitDefs[targetDefID]
                if targetDef and not restricted[targetDef.name] then
                    local tx, ty, tz = Spring.GetUnitPosition(targetID)
                    if tx then
                        local dx = ux - tx
                        local dz = uz - tz
                        local distSq = dx * dx + dz * dz
                        if distSq < nearestDistSq then
                            nearestDistSq = distSq
                            nearestTarget = targetID
                        end
                    end
                end
            end
        end
    end

    return nearestTarget
end

function gadget:AllowCommand(unitID, unitDefID, unitTeam, cmdID, cmdParams, cmdOptions)
    local restricted = restrictedTargetLookup[tostring(unitTeam)]
    if not restricted then
        return true
    end

    if cmdID == CMD.ATTACK or cmdID == CMD.FIGHT or cmdID == CMD.MANUALFIRE then
        if cmdParams and #cmdParams == 1 then
            local targetID = cmdParams[1]
            if Spring.ValidUnitID(targetID) then
                local targetDefID = Spring.GetUnitDefID(targetID)
                if targetDefID then
                    local targetDef = UnitDefs[targetDefID]
                    if targetDef and restricted[targetDef.name] then
                        local newTarget = findNearestValidTarget(unitID, unitTeam, restricted)
                        if newTarget then
                            Spring.GiveOrderToUnit(unitID, CMD.ATTACK, {newTarget}, {})
                        else
                            Spring.GiveOrderToUnit(unitID, CMD.STOP, {}, {})
                        end
                        return false
                    end
                end
            end
        end
    end

    return true
end
