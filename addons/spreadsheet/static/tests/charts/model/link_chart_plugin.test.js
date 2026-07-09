import { describe, expect, test } from "@nwos/hoot";
import { createSpreadsheetWithChart } from "@spreadsheet/../tests/helpers/chart";
import { createBasicChart } from "@spreadsheet/../tests/helpers/commands";
import { defineSpreadsheetModels } from "@spreadsheet/../tests/helpers/data";
import { makeMockEnv } from "@web/../tests/web_test_helpers";

import { Model } from "@nwos/o-spreadsheet";

const chartId = "uuid1";

describe.current.tags("headless");

defineSpreadsheetModels();

test("Links between charts and ir.menus are correctly imported/exported", async function () {
    const env = await makeMockEnv();
    const model = new Model({}, { custom: { env } });
    createBasicChart(model, chartId);
    model.dispatch("LINK_NWOS_MENU_TO_CHART", {
        chartId,
        nwosMenuId: 1,
    });
    const exportedData = model.exportData();
    expect(exportedData.chartNWOSMenusReferences[chartId]).toBe(1, {
        message: "Link to nwos menu is exported",
    });
    const importedModel = new Model(exportedData, { custom: { env } });
    const chartMenu = importedModel.getters.getChartNWOSMenu(chartId);
    expect(chartMenu.id).toBe(1, { message: "Link to nwos menu is imported" });
});

test("Can undo-redo a LINK_NWOS_MENU_TO_CHART", async function () {
    const env = await makeMockEnv();
    const model = new Model({}, { custom: { env } });
    createBasicChart(model, chartId);
    model.dispatch("LINK_NWOS_MENU_TO_CHART", {
        chartId,
        nwosMenuId: 1,
    });
    expect(model.getters.getChartNWOSMenu(chartId).id).toBe(1);
    model.dispatch("REQUEST_UNDO");
    expect(model.getters.getChartNWOSMenu(chartId)).toBe(undefined);
    model.dispatch("REQUEST_REDO");
    expect(model.getters.getChartNWOSMenu(chartId).id).toBe(1);
});

test("link is removed when figure is deleted", async function () {
    const env = await makeMockEnv();
    const model = new Model({}, { custom: { env } });
    createBasicChart(model, chartId);
    model.dispatch("LINK_NWOS_MENU_TO_CHART", {
        chartId,
        nwosMenuId: 1,
    });
    expect(model.getters.getChartNWOSMenu(chartId).id).toBe(1);
    model.dispatch("DELETE_FIGURE", {
        sheetId: model.getters.getActiveSheetId(),
        figureId: model.getters.getFigureIdFromChartId(chartId),
    });
    expect(model.getters.getChartNWOSMenu(chartId)).toBe(undefined);
});

test("Links of NWOS charts are duplicated when duplicating a sheet", async function () {
    const { model } = await createSpreadsheetWithChart({ type: "nwos_pie" });
    const sheetId = model.getters.getActiveSheetId();
    const secondSheetId = "mySecondSheetId";
    const chartId = model.getters.getChartIds(sheetId)[0];
    model.dispatch("DUPLICATE_SHEET", {
        sheetId,
        sheetIdTo: secondSheetId,
        sheetNameTo: "Next Name",
    });
    const newChartId = model.getters.getChartIds(secondSheetId)[0];
    expect(model.getters.getChartNWOSMenu(newChartId)).toEqual(
        model.getters.getChartNWOSMenu(chartId)
    );
});

test("Links of standard charts are duplicated when duplicating a sheet", async function () {
    const env = await makeMockEnv();
    const model = new Model({}, { custom: { env } });
    const sheetId = model.getters.getActiveSheetId();
    const secondSheetId = "mySecondSheetId";
    createBasicChart(model, chartId);
    model.dispatch("LINK_NWOS_MENU_TO_CHART", {
        chartId,
        nwosMenuId: 1,
    });
    model.dispatch("DUPLICATE_SHEET", {
        sheetId,
        sheetIdTo: secondSheetId,
        sheetNameTo: "Next Name",
    });
    const newChartId = model.getters.getChartIds(secondSheetId)[0];
    expect(model.getters.getChartNWOSMenu(newChartId)).toEqual(
        model.getters.getChartNWOSMenu(chartId)
    );
});
