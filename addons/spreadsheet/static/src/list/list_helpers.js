// @ts-check

import { helpers } from "@nwos/o-spreadsheet";

const { getFunctionsFromTokens } = helpers;

/** @typedef {import("@nwos/o-spreadsheet").Token} Token */

/**
 * Parse a spreadsheet formula and detect the number of LIST functions that are
 * present in the given formula.
 *
 * @param {Token[]} tokens
 *
 * @returns {number}
 */
export function getNumberOfListFormulas(tokens) {
    return getFunctionsFromTokens(tokens, ["NWOS.LIST", "NWOS.LIST.HEADER"]).length;
}

/**
 * Get the first List function description of the given formula.
 *
 * @param {Token[]} tokens
 *
 * @returns {import("../helpers/nwos_functions_helpers").NWOSFunctionDescription|undefined}
 */
export function getFirstListFunction(tokens) {
    return getFunctionsFromTokens(tokens, ["NWOS.LIST", "NWOS.LIST.HEADER"])[0];
}
