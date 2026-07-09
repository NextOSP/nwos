import { FieldMatching } from "./global_filter.d";
import {
    CorePlugin,
    UIPlugin,
    DispatchResult,
    CommandResult,
    AddPivotCommand,
    UpdatePivotCommand,
    CancelledReason,
} from "@nwos/o-spreadsheet";
import * as NWOSCancelledReason from "@spreadsheet/o_spreadsheet/cancelled_reason";

type CoreDispatch = CorePlugin["dispatch"];
type UIDispatch = UIPlugin["dispatch"];
type CoreCommand = Parameters<CorePlugin["allowDispatch"]>[0];
type Command = Parameters<UIPlugin["allowDispatch"]>[0];

// TODO look for a way to remove this and use the real import * as NWOSCancelledReason
type NWOSCancelledReason = string;

declare module "@spreadsheet" {
    interface NWOSCommandDispatcher {
        dispatch<T extends NWOSCommandTypes, C extends Extract<NWOSCommand, { type: T }>>(
            type: {} extends Omit<C, "type"> ? T : never
        ): NWOSDispatchResult;
        dispatch<T extends NWOSCommandTypes, C extends Extract<NWOSCommand, { type: T }>>(
            type: T,
            r: Omit<C, "type">
        ): NWOSDispatchResult;
    }

    interface NWOSCoreCommandDispatcher {
        dispatch<T extends NWOSCoreCommandTypes, C extends Extract<NWOSCoreCommand, { type: T }>>(
            type: {} extends Omit<C, "type"> ? T : never
        ): NWOSDispatchResult;
        dispatch<T extends NWOSCoreCommandTypes, C extends Extract<NWOSCoreCommand, { type: T }>>(
            type: T,
            r: Omit<C, "type">
        ): NWOSDispatchResult;
    }

    interface NWOSDispatchResult extends DispatchResult {
        readonly reasons: (CancelledReason | NWOSCancelledReason)[];
        isCancelledBecause(reason: CancelledReason | NWOSCancelledReason): boolean;
    }

    type NWOSCommandTypes = NWOSCommand["type"];
    type NWOSCoreCommandTypes = NWOSCoreCommand["type"];

    type NWOSDispatch = UIDispatch & NWOSCommandDispatcher["dispatch"];
    type NWOSCoreDispatch = CoreDispatch & NWOSCoreCommandDispatcher["dispatch"];

    // CORE

    export interface ExtendedAddPivotCommand extends AddPivotCommand {
        pivot: ExtendedPivotCoreDefinition;
    }

    export interface ExtendedUpdatePivotCommand extends UpdatePivotCommand {
        pivot: ExtendedPivotCoreDefinition;
    }

    export interface AddThreadCommand {
        type: "ADD_COMMENT_THREAD";
        threadId: number;
        sheetId: string;
        col: number;
        row: number;
    }

    export interface EditThreadCommand {
        type: "EDIT_COMMENT_THREAD";
        threadId: number;
        sheetId: string;
        col: number;
        row: number;
        isResolved: boolean;
    }

    export interface DeleteThreadCommand {
        type: "DELETE_COMMENT_THREAD";
        threadId: number;
        sheetId: string;
        col: number;
        row: number;
    }

    // this command is deprecated. use UPDATE_PIVOT instead
    export interface UpdatePivotDomainCommand {
        type: "UPDATE_NWOS_PIVOT_DOMAIN";
        pivotId: string;
        domain: Array;
    }

    export interface AddGlobalFilterCommand {
        type: "ADD_GLOBAL_FILTER";
        filter: CmdGlobalFilter;
        [string]: any; // Fields matching
    }

    export interface EditGlobalFilterCommand {
        type: "EDIT_GLOBAL_FILTER";
        filter: CmdGlobalFilter;
        [string]: any; // Fields matching
    }

    export interface RemoveGlobalFilterCommand {
        type: "REMOVE_GLOBAL_FILTER";
        id: string;
    }

    export interface MoveGlobalFilterCommand {
        type: "MOVE_GLOBAL_FILTER";
        id: string;
        delta: number;
    }

    // UI

    export interface RefreshAllDataSourcesCommand {
        type: "REFRESH_ALL_DATA_SOURCES";
    }

    export interface SetGlobalFilterValueCommand {
        type: "SET_GLOBAL_FILTER_VALUE";
        id: string;
        value: any;
    }

    export interface SetManyGlobalFilterValueCommand {
        type: "SET_MANY_GLOBAL_FILTER_VALUE";
        filters: { filterId: string; value: any }[];
    }

    type NWOSCoreCommand =
        | ExtendedAddPivotCommand
        | ExtendedUpdatePivotCommand
        | UpdatePivotDomainCommand
        | AddThreadCommand
        | DeleteThreadCommand
        | EditThreadCommand
        | AddGlobalFilterCommand
        | EditGlobalFilterCommand
        | RemoveGlobalFilterCommand
        | MoveGlobalFilterCommand;

    export type AllCoreCommand = NWOSCoreCommand | CoreCommand;

    type NWOSLocalCommand =
        | RefreshAllDataSourcesCommand
        | SetGlobalFilterValueCommand
        | SetManyGlobalFilterValueCommand;

    type NWOSCommand = NWOSCoreCommand | NWOSLocalCommand;

    export type AllCommand = NWOSCommand | Command;
}
