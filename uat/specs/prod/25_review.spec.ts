import { test, expect, read, loginAsAdmin } from '../../fixtures/prod';
import { OdooUi } from '../../pages/prod';

/**
 * The quarterly appraisal the department's own regulation asks for.
 *
 * Regulation 01/TTNTDVS scores a quarter out of 100: discipline 30, KPI
 * results 60, bonus for exceeding KPIs 10. The questionnaire, the template
 * with its four stages (self, manager, calibration, final), the review cycle
 * for Q3/2026 and one review per person are entered here through the screens
 * a performance manager uses. The KPI part is not typed in: each review reads
 * the monthly scorecards of the quarter and a manager fixes that figure onto
 * the review, which is what the appraisal is then signed on.
 *
 * Reruns are safe: everything is found by name first.
 */

const QUESTIONNAIRE = 'Phiếu đánh giá Quý — Quy chế 01/TTNTDVS';
const TEMPLATE = 'Đánh giá quý — Phòng Kinh doanh và Dịch vụ';
const CYCLE = 'Đánh giá Quý III/2026 — Phòng Kinh doanh và Dịch vụ';
const PERF_CYCLE = 'KDDV-2026-Q3';
const DEPARTMENT = 'Kinh doanh và Dịch vụ';

const SECTIONS: { name: string; questions: [string, string][] }[] = [
  {
    name: 'A. Ý thức và kỷ luật (30 điểm)',
    questions: [
      ['Chấp hành nội quy, giờ làm việc và quy định của Trung tâm', 'rating_10'],
      ['Tinh thần phối hợp, hỗ trợ đồng nghiệp', 'rating_10'],
      ['Ý thức bảo mật thông tin và tài sản', 'rating_10'],
    ],
  },
  {
    name: 'B. Kết quả KPI (60 điểm) — lấy từ phiếu giao KPI của quý',
    questions: [
      ['Nhận xét của quản lý về kết quả KPI quý (điểm KPI do hệ thống tính)', 'text'],
      ['Kết quả có đúng cam kết đầu quý không', 'rating_10'],
    ],
  },
  {
    name: 'C. Thưởng vượt KPI (10 điểm)',
    questions: [
      ['Đóng góp vượt yêu cầu, sáng kiến, việc phát sinh ngoài KPI', 'rating_10'],
      ['Minh chứng kèm theo', 'text'],
    ],
  },
];

const STAGES: { name: string; type: string; days: number }[] = [
  { name: '1. Cá nhân tự đánh giá', type: 'self', days: 3 },
  { name: '2. Quản lý đánh giá', type: 'manager', days: 3 },
  { name: '3. Hiệu chuẩn', type: 'calibration', days: 2 },
  { name: '4. Chốt kết quả', type: 'final', days: 1 },
];

async function xmlid(name: string): Promise<number> {
  const [module, ref] = name.split('.');
  const [row] = await read('ir.model.data', 'search_read', [[['module', '=', module], ['name', '=', ref]]], { fields: ['res_id'] });
  if (!row) throw new Error(`No record ${name}`);
  return row.res_id;
}

test('quarterly appraisal cycle for the department', async ({ page }) => {
  test.setTimeout(60 * 60_000);
  const ui = new OdooUi(page);
  await loginAsAdmin(page);

  await test.step('questionnaire', async () => {
    if (await read('aic.hrm.review.form', 'search_count', [[['name', '=', QUESTIONNAIRE]]])) return;
    await ui.newRecord(await xmlid('aic_hrm_review.action_review_questionnaire'));
    await ui.fill('name', QUESTIONNAIRE);
    for (const section of SECTIONS) {
      // Adding a section opens its own dialog, and the questions are filled
      // in there before it is saved.
      await page.locator('.o_field_widget[name="section_ids"] .o_field_x2many_list_row_add a').first().click();
      const dialog = page.locator('.modal-dialog').last();
      await dialog.waitFor();
      await ui.fill('name', section.name, dialog);
      for (const [question, type] of section.questions) {
        await dialog.locator('.o_field_widget[name="question_ids"] .o_field_x2many_list_row_add a').first().click();
        const questionRow = dialog.locator('.o_field_widget[name="question_ids"] .o_data_row.o_selected_row').last();
        await questionRow.waitFor();
        await ui.fill('name', question, questionRow);
        await ui.select('aic.hrm.review.question', 'question_type', type, questionRow);
      }
      await dialog.locator('.modal-footer button').filter({ hasText: /^\s*(Lưu & Đóng|Save & Close)\s*$/ }).first().click();
      await expect(dialog).toBeHidden();
    }
    await ui.save(QUESTIONNAIRE);
  });

  const templateAction = await xmlid('aic_hrm_review.action_review_template');
  await test.step('template with its four stages', async () => {
    let [template] = await read('aic.hrm.review.template', 'search_read', [[['name', '=', TEMPLATE]]], { fields: ['stage_ids'] });
    if (!template) {
      const [form] = await read('aic.hrm.review.form', 'search_read', [[['name', '=', QUESTIONNAIRE]]], { fields: ['display_name'] });
      await ui.newRecord(templateAction);
      await ui.fill('name', TEMPLATE);
      await ui.pickMany2one('form_id', form.display_name);
      // The template is saved before its stages: a stage dialog asks which
      // template it belongs to, and an unsaved one cannot answer.
      template = { id: await ui.save(TEMPLATE), stage_ids: [] };
    }
    if (template.stage_ids.length >= STAGES.length) return;
    await ui.openRecord(templateAction, template.id);
    for (const [index, stage] of STAGES.entries()) {
      // Stages, like sections, are entered in their own dialog.
      await page.locator('.o_field_widget[name="stage_ids"] .o_field_x2many_list_row_add a').first().click();
      const dialog = page.locator('.modal-dialog').last();
      await dialog.waitFor();
      await ui.pickMany2one('template_id', TEMPLATE, dialog);
      await ui.fill('sequence', (index + 1) * 10, dialog);
      await ui.fill('name', stage.name, dialog);
      await ui.select('aic.hrm.review.stage', 'stage_type', stage.type, dialog);
      await ui.fill('duration_days', stage.days, dialog);
      await dialog.locator('.modal-footer button')
        .filter({ hasText: /^\s*(Lưu & Đóng|Save & Close)\s*$/ }).first().click();
      await expect(dialog).toBeHidden();
    }
    await ui.save(`${TEMPLATE} stages`);
  });

  const cycleAction = await xmlid('aic_hrm_review.action_review_cycle');
  await test.step('review cycle for Q3/2026', async () => {
    if (await read('aic.hrm.review.cycle', 'search_count', [[['name', '=', CYCLE]]])) return;
    const [perf] = await read('aic.hrm.cycle', 'search_read', [[['code', '=', PERF_CYCLE]]], { fields: ['display_name'] });
    const [template] = await read('aic.hrm.review.template', 'search_read', [[['name', '=', TEMPLATE]]], { fields: ['display_name'] });
    await ui.newRecord(cycleAction);
    await ui.fill('name', CYCLE);
    await ui.pickMany2one('perf_cycle_id', perf.display_name);
    await ui.pickMany2one('template_id', template.display_name);
    await ui.fill('date_start', '01/10/2026');
    await ui.fill('date_end', '15/10/2026');
    await ui.pickMany2one('department_ids', DEPARTMENT);
    await ui.save(CYCLE);
  });

  const [cycle] = await read('aic.hrm.review.cycle', 'search_read', [[['name', '=', CYCLE]]],
    { fields: ['id', 'state', 'review_ids'] });

  await test.step('one review per person of the department', async () => {
    const staff = await read('hr.employee', 'search_count', [[['department_id.name', '=', DEPARTMENT]]]);
    if (cycle.review_ids.length < staff) {
      await ui.openRecord(cycleAction, cycle.id);
      await ui.clickButton('action_generate_reviews', 'generate reviews');
    }
    const reviews = await read('aic.hrm.review', 'search_read', [[['review_cycle_id', '=', cycle.id]]],
      { fields: ['employee_id', 'stage_id'] });
    expect(reviews.length).toBe(staff);
    expect(new Set(reviews.map((r: any) => r.stage_id[1]))).toEqual(new Set([STAGES[0].name]));
  });

  const reviewAction = await xmlid('aic_hrm_review.action_review');
  await test.step('fix the KPI score each appraisal is signed on', async () => {
    const reviews = await read('aic.hrm.review', 'search_read', [[['review_cycle_id', '=', cycle.id]]],
      { fields: ['employee_id', 'goal_score', 'goal_score_live', 'goal_coverage_live', 'goal_score_snapshot_on'] });
    for (const review of reviews) {
      if (review.goal_score_snapshot_on) continue;
      await ui.openRecord(reviewAction, review.id);
      await ui.clickButton('action_refresh_goal_score', `fix goal score ${review.employee_id[1]}`);
    }
  });

  await test.step('read back', async () => {
    const reviews = await read('aic.hrm.review', 'search_read', [[['review_cycle_id', '=', cycle.id]]],
      { fields: ['employee_id', 'goal_score', 'goal_score_live', 'goal_coverage_live',
                 'goal_score_snapshot_on', 'goal_score_snapshot_by', 'stage_id'] });
    for (const review of reviews) {
      const who = review.employee_id[1];
      expect(review.goal_score_snapshot_on, `${who}: the figure must be fixed`).toBeTruthy();
      expect(review.goal_score, `${who}: fixed figure equals the live one`).toBeCloseTo(review.goal_score_live, 6);
    }
    // The department's own numbers: the people with measured KPIs score above
    // zero, and everyone's coverage matches their scorecards.
    const measured = reviews.filter((review: any) => review.goal_coverage_live > 0);
    expect(measured.length).toBeGreaterThan(0);
    expect(measured.every((review: any) => review.goal_score > 0)).toBe(true);
    for (const review of reviews) {
      const cards = await read('aic.hrm.kpi.assignment', 'search_read', [[
        ['employee_id', '=', review.employee_id[0]],
        ['cycle_id.code', 'in', ['KDDV-2026-07', 'KDDV-2026-08', 'KDDV-2026-09']]]],
      { fields: ['data_coverage', 'score_covered'] });
      const coverage = cards.length
        ? cards.reduce((sum: number, card: any) => sum + card.data_coverage, 0) / cards.length : 0;
      expect(review.goal_coverage_live, `${review.employee_id[1]}: coverage`).toBeCloseTo(coverage, 4);
    }
  });
});
