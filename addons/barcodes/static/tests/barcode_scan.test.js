/** @nwos-module **/

import { expect, test } from "@nwos/hoot";
import { waitFor } from "@nwos/hoot-dom";
import { Component, xml } from "@nwos/owl";
import { BarcodeScanner } from "@barcodes/components/barcode_scanner";
import { contains, mountWithCleanup } from "@web/../tests/web_test_helpers";

test.tags("desktop");
test("Display notification for media device permission on barcode scanning", async () => {
    navigator.mediaDevices.getUserMedia = function () {
        return Promise.reject(new DOMException("", "NotAllowedError"));
    };

    class BarcodeScan extends Component {
        static template = xml`
            <div>
                <BarcodeScanner onBarcodeScanned="(ev) => this.onBarcodeScanned(ev)"/>
            </div>
        `;
        static components = { BarcodeScanner };
        static props = ["*"];
    }

    await mountWithCleanup(BarcodeScan);
    await contains("a.o_mobile_barcode").click();
    await waitFor(".modal-body:contains(camera)");
    expect(".modal-body").toHaveText(
        "Unable to access camera\nCould not start scanning. NWOS needs your authorization first."
    );
});
