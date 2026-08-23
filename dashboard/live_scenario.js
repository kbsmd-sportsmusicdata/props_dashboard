(function attachLiveScenarioModel(root) {
    const clamp = (value, low, high) => Math.min(high, Math.max(low, value));
    const isWholeNonNegative = (value) => Number.isInteger(value) && value >= 0;

    function confidenceLabel(probability) {
        const distance = Math.abs(probability - 0.5);
        return distance >= 0.15 ? 'Strong' : distance >= 0.08 ? 'Moderate' : 'Weak';
    }

    function requiredRemaining(line, currentStat) {
        return Math.floor(Number(line)) + 1 - currentStat;
    }

    function asNumber(value) {
        if (value === '' || value === null || value === undefined) return null;
        const number = Number(value);
        return Number.isFinite(number) ? number : null;
    }

    function validateScenario(rawScenario) {
        const errors = [];
        const elapsedMinutes = asNumber(rawScenario?.elapsedMinutes);
        const currentStat = asNumber(rawScenario?.currentStat);
        const teamScore = asNumber(rawScenario?.teamScore);
        const opponentScore = asNumber(rawScenario?.opponentScore);
        const playerMinutes = asNumber(rawScenario?.playerMinutes);

        if (elapsedMinutes === null || !(elapsedMinutes > 0 && elapsedMinutes < 40)) {
            errors.push('Elapsed minutes must be greater than 0 and less than 40.');
        }
        if (!isWholeNonNegative(currentStat)) errors.push('Current stat must be a non-negative whole number.');
        if (!isWholeNonNegative(teamScore)) errors.push('Team score must be a non-negative whole number.');
        if (!isWholeNonNegative(opponentScore)) errors.push('Opponent score must be a non-negative whole number.');
        if (playerMinutes !== null && (playerMinutes < 0 || (elapsedMinutes !== null && playerMinutes > elapsedMinutes))) {
            errors.push('Player minutes must be between 0 and elapsed minutes.');
        }

        return errors.length
            ? { valid: false, errors }
            : { valid: true, errors: [], value: { elapsedMinutes, currentStat, teamScore, opponentScore, playerMinutes } };
    }

    function validLiveModel(model) {
        const numericFields = ['season_mean', 'season_std', 'team_scoring_avg', 'league_total_scoring_avg'];
        return model
            && Array.isArray(model.historical_totals)
            && model.historical_totals.length > 0
            && numericFields.every((field) => Number.isFinite(Number(model[field])))
            && Number(model.season_mean) >= 0
            && Number(model.season_std) >= 0
            && Number(model.league_total_scoring_avg) > 0;
    }

    function poissonSurvival(required, mean) {
        if (required <= 0) return 1;
        if (!(mean > 0)) return 0;
        let term = Math.exp(-mean);
        let cdf = term;
        for (let count = 1; count < required; count += 1) {
            term *= mean / count;
            cdf += term;
        }
        return clamp(1 - cdf, 0, 1);
    }

    function erf(value) {
        const sign = value < 0 ? -1 : 1;
        const x = Math.abs(value);
        const t = 1 / (1 + 0.3275911 * x);
        const y = 1 - (((((1.061405429 * t - 1.453152027) * t + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t) * Math.exp(-x * x);
        return sign * y;
    }

    function normalSurvival(value, mean, standardDeviation) {
        if (!(standardDeviation > 0)) return mean > value ? 1 : 0;
        const z = (value - mean) / (standardDeviation * Math.sqrt(2));
        return clamp(0.5 * (1 - erf(z)), 0, 1);
    }

    function calculate(model, rawScenario, line) {
        const validated = validateScenario(rawScenario);
        if (!validated.valid) return { active: false, errors: validated.errors };
        if (!validLiveModel(model) || !Number.isFinite(Number(line))) {
            return { active: false, errors: ['Historical live-model data is not available for this market.'] };
        }

        const scenario = validated.value;
        const elapsedShare = scenario.elapsedMinutes / 40;
        const remainingShare = 1 - elapsedShare;
        const baseRemainingMean = Number(model.season_mean) * remainingShare;
        const baseRemainingStd = Number(model.season_std) * Math.sqrt(remainingShare);
        const paceMultiplier = clamp(
            ((scenario.teamScore + scenario.opponentScore) / scenario.elapsedMinutes) /
                (Number(model.league_total_scoring_avg) / 40),
            0.85,
            1.15,
        );
        const scoreMargin = scenario.teamScore - scenario.opponentScore;
        const marginMultiplier = clamp(
            1 - Math.sign(scoreMargin) * Math.max(0, Math.abs(scoreMargin) - 9) * 0.005,
            0.95,
            1.05,
        );
        const minuteMultiplier = scenario.playerMinutes && scenario.playerMinutes > 0
            ? clamp((scenario.currentStat / scenario.playerMinutes) / (Number(model.season_mean) / 40 || 1), 0.85, 1.15)
            : 1;
        const contextMultiplier = paceMultiplier * marginMultiplier * minuteMultiplier;
        const adjustedRemainingMean = baseRemainingMean * contextMultiplier;
        const adjustedRemainingStd = Math.max(0.25, baseRemainingStd * paceMultiplier * minuteMultiplier);
        const remaining = requiredRemaining(line, scenario.currentStat);
        const alreadyOver = remaining <= 0;
        const empirical = alreadyOver ? 1 : clamp(
            model.historical_totals
                .map((total) => scenario.currentStat + (Number(total) - Number(model.season_mean) * elapsedShare) * contextMultiplier)
                .filter((projectedFinal) => projectedFinal > Number(line)).length / model.historical_totals.length,
            0,
            1,
        );
        const poisson = alreadyOver ? 1 : poissonSurvival(remaining, adjustedRemainingMean);
        const normal = alreadyOver ? 1 : normalSurvival(remaining, adjustedRemainingMean, adjustedRemainingStd);
        const ensemble = clamp((empirical + poisson + normal) / 3, 0, 1);

        return {
            active: true,
            errors: [],
            requiredRemaining: Math.max(0, remaining),
            remainingMinutes: 40 - scenario.elapsedMinutes,
            paceMultiplier,
            marginMultiplier,
            minuteMultiplier,
            adjustedRemainingMean,
            adjustedRemainingStd,
            prob_empirical: empirical,
            prob_poisson: poisson,
            prob_normal: normal,
            prob_ensemble: ensemble,
            edge_direction: ensemble >= 0.5 ? 'OVER' : 'UNDER',
            edge_strength: confidenceLabel(ensemble),
        };
    }

    root.LiveScenarioModel = { calculate, requiredRemaining, validateScenario };
}(globalThis));
