import { resetAll, seedAll, target } from './fixtures/rpc';

/**
 * Put the database in a known state before anything runs.
 *
 * Reset first, then seed. Re-seeding alone would be faster and would also be
 * a lie: a run that starts on top of whatever the last run left behind cannot
 * tell a fixed bug from a leftover record.
 */
export default async function globalSetup() {
  if (!target.db.includes('UAT')) {
    throw new Error(
      `Refusing to seed "${target.db}". This harness creates and deletes ` +
      'business data and may only ever point at a UAT database.');
  }
  const removed = await resetAll();
  const seeded = await seedAll();
  const names = Object.keys(seeded).sort();
  console.log(
    `[uat] ${target.db} @ ${target.url}: cleared ${removed.records_removed} ` +
    `record(s), seeded ${names.length} fixtures`);
}
