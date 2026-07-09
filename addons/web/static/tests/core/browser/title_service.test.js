import { beforeEach, describe, expect, test } from "@nwos/hoot";
import { getService, makeMockEnv } from "@web/../tests/web_test_helpers";

describe.current.tags("headless");

let titleService;

beforeEach(async () => {
    await makeMockEnv();
    titleService = getService("title");
});

test("simple title", () => {
    titleService.setParts({ one: "MyNWOS" });
    expect(titleService.current).toBe("MyNWOS");
});

test("add title part", () => {
    titleService.setParts({ one: "MyNWOS", two: null });
    expect(titleService.current).toBe("MyNWOS");
    titleService.setParts({ three: "Import" });
    expect(titleService.current).toBe("MyNWOS - Import");
});

test("modify title part", () => {
    titleService.setParts({ one: "MyNWOS" });
    expect(titleService.current).toBe("MyNWOS");
    titleService.setParts({ one: "Znwos" });
    expect(titleService.current).toBe("Znwos");
});

test("delete title part", () => {
    titleService.setParts({ one: "MyNWOS" });
    expect(titleService.current).toBe("MyNWOS");
    titleService.setParts({ one: null });
    expect(titleService.current).toBe("NWOS");
});

test("all at once", () => {
    titleService.setParts({ one: "MyNWOS", two: "Import" });
    expect(titleService.current).toBe("MyNWOS - Import");
    titleService.setParts({ one: "Znwos", two: null, three: "Sauron" });
    expect(titleService.current).toBe("Znwos - Sauron");
});

test("get title parts", () => {
    expect(titleService.current).toBe("");
    titleService.setParts({ one: "MyNWOS", two: "Import" });
    expect(titleService.current).toBe("MyNWOS - Import");
    const parts = titleService.getParts();
    expect(parts).toEqual({ one: "MyNWOS", two: "Import" });
    parts.action = "Export";
    expect(titleService.current).toBe("MyNWOS - Import"); // parts is a copy!
});
