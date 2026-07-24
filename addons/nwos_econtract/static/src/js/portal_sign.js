// eContract portal signing page enhancement (plain script, not an odoo-module).
// The signature_pad UMD bundled before this file exposes window.SignaturePad.
(function () {
    "use strict";

    function initEcontractSign() {
        var form = document.querySelector(".o_econtract_sign_form");
        if (!form || typeof window.SignaturePad === "undefined") {
            return;
        }
        var canvas = form.querySelector(".o_sign_pad");
        var dataInput = form.querySelector(".o_sign_data");
        var clearBtn = form.querySelector(".o_sign_clear");
        if (!canvas || !dataInput) {
            return;
        }

        var pad = new window.SignaturePad(canvas, {
            penColor: "#000000",
            backgroundColor: "rgba(255,255,255,0)",
        });

        function resize() {
            var ratio = Math.max(window.devicePixelRatio || 1, 1);
            var rect = canvas.getBoundingClientRect();
            if (rect.width) {
                canvas.width = rect.width * ratio;
                canvas.height = 180 * ratio;
                canvas.getContext("2d").scale(ratio, ratio);
            }
            pad.clear();
        }

        window.addEventListener("resize", resize);
        resize();

        if (clearBtn) {
            clearBtn.addEventListener("click", function () {
                pad.clear();
            });
        }

        form.addEventListener("submit", function (ev) {
            if (pad.isEmpty()) {
                ev.preventDefault();
                var warn = form.querySelector(".o_sign_warning");
                if (!warn) {
                    warn = document.createElement("div");
                    warn.className = "o_sign_warning text-danger mt-2";
                    warn.textContent = "Please draw your signature before submitting.";
                    form.appendChild(warn);
                }
                return;
            }
            dataInput.value = pad.toDataURL("image/png");
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initEcontractSign);
    } else {
        initEcontractSign();
    }
})();
