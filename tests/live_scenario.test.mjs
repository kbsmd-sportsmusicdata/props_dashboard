import assert from "node:assert/strict";
import "../dashboard/live_scenario.js";

const model = {
  season_mean: 18,
  season_std: 5,
  games_played: 6,
  historical_totals: [12, 15, 17, 18, 20, 26],
  season_minutes_avg: 32,
  team_scoring_avg: 82,
  league_total_scoring_avg: 160,
};

const halftime = globalThis.LiveScenarioModel.calculate(model, {
  elapsedMinutes: 20,
  currentStat: 9,
  teamScore: 42,
  opponentScore: 39,
}, 15.5);

assert.equal(halftime.active, true);
assert.equal(halftime.requiredRemaining, 7);
assert.equal(halftime.remainingMinutes, 20);
for (const key of ["prob_empirical", "prob_poisson", "prob_normal", "prob_ensemble"]) {
  assert.ok(halftime[key] >= 0 && halftime[key] <= 1, `${key} must be a probability`);
}

const alreadyOver = globalThis.LiveScenarioModel.calculate(model, {
  elapsedMinutes: 20,
  currentStat: 16,
  teamScore: 42,
  opponentScore: 39,
  playerMinutes: 19,
}, 15.5);
assert.equal(alreadyOver.prob_ensemble, 1);

const normalPerMinuteRate = globalThis.LiveScenarioModel.calculate(model, {
  elapsedMinutes: 20,
  currentStat: 9,
  teamScore: 42,
  opponentScore: 39,
  playerMinutes: 16,
}, 15.5);
assert.equal(normalPerMinuteRate.minuteMultiplier, 1);

const invalid = globalThis.LiveScenarioModel.calculate(model, {
  elapsedMinutes: 40,
  currentStat: 9,
  teamScore: 42,
  opponentScore: 39,
}, 15.5);
assert.equal(invalid.active, false);
assert.match(invalid.errors.join(" "), /less than 40/);
