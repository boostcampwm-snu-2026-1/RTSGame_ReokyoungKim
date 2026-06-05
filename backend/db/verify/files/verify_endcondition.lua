function gadget:GetInfo()
    return {
        name    = "Verify End Condition",
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
local gameEndDetected = false
local victoryCondition = nil
local defeatCondition = nil

function gadget:Initialize()
    if not config then
        Spring.Echo("[FEEDBACK] No config available")
        testState = "failed"
        return
    end

    local endCondition = config.end_condition
    if not endCondition then
        Spring.Echo("[FEEDBACK] No end_condition in config")
        testState = "failed"
        return
    end

    victoryCondition = endCondition.victory_condition
    defeatCondition = endCondition.defeat_condition
end

function gadget:GameStart()
    testStartFrame = Spring.GetGameFrame()
    testState = "setup"
end

local function parseCondition(condStr)
    local unitName, op, value = condStr:match("(%w+)%s*([=<>!]+)%s*(%d+)")
    if unitName and op and value then
        return {
            unitName = unitName,
            op = op,
            value = tonumber(value)
        }
    end
    return nil
end

local function getTeamUnitCountByName(teamID, unitName)
    local unitDef = UnitDefNames[unitName]
    if not unitDef then return 0 end

    local units = Spring.GetTeamUnitsByDefs(teamID, unitDef.id)
    return units and #units or 0
end

local function evaluateCondition(cond, op, value, actual)
    if op == "==" then
        return actual == value
    elseif op == "!=" then
        return actual ~= value
    elseif op == "<" then
        return actual < value
    elseif op == "<=" then
        return actual <= value
    elseif op == ">" then
        return actual > value
    elseif op == ">=" then
        return actual >= value
    end
    return false
end

local function checkConditionSet(conditionSet)
    if not conditionSet or #conditionSet < 2 then
        return false, "Invalid condition format"
    end

    local operator = conditionSet[1]
    local results = {}

    for i = 2, #conditionSet do
        local teamConditions = conditionSet[i]
        for teamIDStr, conditions in pairs(teamConditions) do
            local teamID = tonumber(teamIDStr)
            for _, condStr in ipairs(conditions) do
                local parsed = parseCondition(condStr)
                if parsed then
                    local actual = getTeamUnitCountByName(teamID, parsed.unitName)
                    local result = evaluateCondition(parsed, parsed.op, parsed.value, actual)
                    table.insert(results, {
                        teamID = teamID,
                        condition = condStr,
                        expected = parsed.value,
                        actual = actual,
                        passed = result
                    })
                end
            end
        end
    end

    if operator == "and" then
        for _, r in ipairs(results) do
            if not r.passed then
                return false, results
            end
        end
        return true, results
    elseif operator == "or" then
        for _, r in ipairs(results) do
            if r.passed then
                return true, results
            end
        end
        return false, results
    end

    return false, results
end

local function setupTest()
    if not victoryCondition and not defeatCondition then
        Spring.Echo("[FEEDBACK] No victory or defeat conditions defined")
        return false
    end
    return true
end

function gadget:TeamDied(teamID)
    gameEndDetected = true
end

function gadget:GameOver(winningAllyTeams)
    gameEndDetected = true
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
        local waitFrames = 150
        if frame - testStartFrame > waitFrames then
            local hasError = false

            if victoryCondition then
                local victoryMet, victoryResults = checkConditionSet(victoryCondition)
                if not victoryMet then
                    for _, r in ipairs(victoryResults) do
                        if not r.passed then
                            Spring.Echo(string.format("[FEEDBACK] Victory condition not met - Team %d: %s (actual: %d)",
                                r.teamID, r.condition, r.actual))
                        end
                    end
                end
            end

            if defeatCondition then
                local defeatMet, defeatResults = checkConditionSet(defeatCondition)
                if defeatMet then
                    for _, r in ipairs(defeatResults) do
                        if r.passed then
                            Spring.Echo(string.format("[FEEDBACK] Defeat condition triggered - Team %d: %s (actual: %d)",
                                r.teamID, r.condition, r.actual))
                            hasError = true
                        end
                    end
                end
            end

            if hasError then
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
