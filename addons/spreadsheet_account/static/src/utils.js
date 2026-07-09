// @ts-check

import { helpers } from "@nwos/o-spreadsheet";

const { getFunctionsFromTokens } = helpers;

/**
 * @typedef {import("@nwos/o-spreadsheet").Token} Token
 * @typedef  {import("@spreadsheet/helpers/nwos_functions_helpers").NWOSFunctionDescription} NWOSFunctionDescription
 */

/**
 * @param {Token[]} tokens
 * @returns {number}
 */
export function getNumberOfAccountFormulas(tokens) {
    return getFunctionsFromTokens(tokens, ["NWOS.BALANCE", "NWOS.CREDIT", "NWOS.DEBIT", "NWOS.RESIDUAL", "NWOS.PARTNER.BALANCE", "NWOS.BALANCE.TAG"]).length;
}

/**
 * Get the first Account function description of the given formula.
 *
 * @param {Token[]} tokens
 * @returns {NWOSFunctionDescription | undefined}
 */
export function getFirstAccountFunction(tokens) {
    return getFunctionsFromTokens(tokens, ["NWOS.BALANCE", "NWOS.CREDIT", "NWOS.DEBIT", "NWOS.RESIDUAL", "NWOS.PARTNER.BALANCE", "NWOS.BALANCE.TAG"])[0];
}
