/** @odoo-module **/
// Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.

/**
 * Which cycle a dashboard should open on.
 *
 * The newest cycle is usually the month that has just started: it carries
 * scorecards but no objectives, so a screen that opens on it greets its
 * reader with an empty page and they conclude the system holds nothing. Open
 * on the newest cycle that actually has objectives, and fall back to the
 * newest one when none of them has any.
 *
 * Shared by the leadership cockpit and the alignment tree, because two
 * screens disagreeing about which cycle to show is worse than either choice.
 */
export async function cycleWithObjectives(orm, cycles) {
    if (!cycles.length) {
        return false;
    }
    const counts = await orm.formattedReadGroup(
        "aic.hrm.objective",
        [["cycle_id", "in", cycles.map((cycle) => cycle.id)]],
        ["cycle_id"],
        ["__count"],
    );
    const withObjectives = new Set(
        counts.map((group) => group.cycle_id && group.cycle_id[0]));
    const first = cycles.find((cycle) => withObjectives.has(cycle.id));
    return (first || cycles[0]).id;
}
