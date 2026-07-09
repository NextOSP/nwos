import { BaseOptionComponent } from "@html_builder/core/utils";
import { useState } from "@nwos/owl";

export class TranslateWebpageOption extends BaseOptionComponent {
    static template = "website.TranslateWebpageOption";
    static selector = "*";
    setup() {
        super.setup();
        this.translationState = useState(
            this.env.editor.shared.customizeTranslationTab.getTranslationState()
        );
    }
}
