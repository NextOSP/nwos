import { _t } from "@web/core/l10n/translation";
import { formatAST, toPyValue } from "@web/core/py_js/py_utils";
import { MultiRecordSelector } from "@web/core/record_selectors/multi_record_selector";
import { RecordSelector } from "@web/core/record_selectors/record_selector";
import { Expression } from "@web/core/tree_editor/condition_tree";
import { isId } from "@web/core/tree_editor/utils";
import { user } from "@web/core/user";
import { imageUrl } from "@web/core/utils/urls";

function isCurrentUserExpression(val, resModel) {
    return resModel === "res.users" && (val instanceof Expression ? String(val) : val) === "uid";
}

export const getFormat = (val, displayNames, resModel) => {
    let text;
    let colorIndex;
    if (isId(val)) {
        text =
            typeof displayNames[val] === "string"
                ? displayNames[val]
                : _t("Inaccessible/missing record ID: %s", val);
        colorIndex = typeof displayNames[val] === "string" ? 0 : 2; // 0 = grey, 2 = orange
    } else if (isCurrentUserExpression(val, resModel)) {
        text = user.name || _t("Current user");
        colorIndex = 0;
    } else {
        text =
            val instanceof Expression
                ? String(val)
                : _t("Invalid record ID: %s", formatAST(toPyValue(val)));
        colorIndex = val instanceof Expression ? 2 : 1; // 1 = red
    }
    return { text, colorIndex };
};

export class DomainSelectorAutocomplete extends MultiRecordSelector {
    static props = {
        ...MultiRecordSelector.props,
        resIds: true, //resIds could be an array of ids or an array of expressions
    };

    getIds(props = this.props) {
        return props.resIds.filter((val) => isId(val));
    }

    getTags(props, displayNames) {
        return props.resIds.map((val, index) => {
            const { text, colorIndex } = getFormat(val, displayNames, props.resModel);
            return {
                text,
                colorIndex,
                onDelete: () => {
                    this.props.update([
                        ...this.props.resIds.slice(0, index),
                        ...this.props.resIds.slice(index + 1),
                    ]);
                },
                img:
                    this.isAvatarModel &&
                    isId(val) &&
                    imageUrl(this.props.resModel, val, "avatar_128"),
            };
        });
    }
}

export class DomainSelectorSingleAutocomplete extends RecordSelector {
    static props = {
        ...RecordSelector.props,
        resId: true,
    };

    getDisplayName(props = this.props, displayNames) {
        const { resId } = props;
        if (resId === false) {
            return "";
        }
        const { text } = getFormat(resId, displayNames, props.resModel);
        return text;
    }

    getIds(props = this.props) {
        if (isId(props.resId)) {
            return [props.resId];
        }
        return [];
    }
}
