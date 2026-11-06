import { render, screen, waitFor, within } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "#lib/api/client.ts";
import type { DeviceOut, PrinterOut, ReviewOut, UserOut } from "#lib/api/types.ts";
import type { Role } from "#lib/roles.ts";
import { event, product, spoolDetail, spoolRow } from "../test/fixtures.ts";

const nav = vi.hoisted(() => ({ goto: vi.fn() }));
vi.mock("$app/navigation", () => ({ goto: nav.goto }));

const admin = vi.hoisted(() => ({
  getReview: vi.fn(),
  acceptEvent: vi.fn(),
  unacceptEvent: vi.fn(),
  dismissTag: vi.fn(),
  restoreTag: vi.fn(),
  listEvents: vi.fn(),
  listProducts: vi.fn(),
  createProduct: vi.fn(),
  addSpool: vi.fn(),
  listDevices: vi.fn(),
  registerDevice: vi.fn(),
  rotateToken: vi.fn(),
  revokeDevice: vi.fn(),
  listUsers: vi.fn(),
  createUser: vi.fn(),
  updateUser: vi.fn(),
  changePassword: vi.fn(),
  dismissLikelyEmpty: vi.fn(),
  restoreLikelyEmpty: vi.fn(),
  listPrinters: vi.fn(),
  unpinPrinter: vi.fn(),
}));
vi.mock("#lib/api/admin.ts", () => admin);

const stock = vi.hoisted(() => ({
  undoEvent: vi.fn(),
  recordAction: vi.fn(),
  reviewCount: vi.fn(),
  waitingIn: (r: ReviewOut) =>
    r.flagged_events.length + r.unidentified_tags.length + r.likely_empty.length,
}));
vi.mock("#lib/api/stock.ts", () => stock);

const { session } = await import("#lib/auth/session.svelte.ts");
const { reviewBadge } = await import("#lib/review-badge.svelte.ts");
const ReviewPage = (await import("./review/+page.svelte")).default;
const ActivityPage = (await import("./activity/+page.svelte")).default;
const NewSpoolPage = (await import("./spools/new/+page.svelte")).default;
const DevicesPage = (await import("./devices/+page.svelte")).default;
const UsersPage = (await import("./users/+page.svelte")).default;
const AccountPage = (await import("./account/+page.svelte")).default;

function signedInAs(role: Role): void {
  session.user = { id: 1, username: "frank", role };
  session.loaded = true;
}

beforeEach(() => signedInAs("admin"));
afterEach(() => vi.resetAllMocks());

const UNREADABLE = {
  uid: "A1B2",
  first_seen_at: "2026-11-03T20:44:00Z",
  readable: false,
  decoded: null,
};

function review(overrides: Partial<ReviewOut> = {}): ReviewOut {
  return {
    flagged_events: [event({ id: "f1", type: "empty", flagged: true, spool_id: 10 })],
    unidentified_tags: [UNREADABLE],
    likely_empty: [],
    ...overrides,
  };
}

describe("Review page", () => {
  it("lists each section and sets the header count", async () => {
    admin.getReview.mockResolvedValue(review());
    render(ReviewPage);

    expect(await screen.findByRole("heading", { name: "Used up, flagged" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Unreadable tag" })).toBeInTheDocument();
    expect(screen.getByText(/No suggestions\./)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open spool" })).toHaveAttribute("href", "/spools/10");
    expect(reviewBadge.count).toBe(2);
  });

  it("accepts a flagged event, then brings it back", async () => {
    admin.getReview
      .mockResolvedValueOnce(review())
      .mockResolvedValueOnce(review({ flagged_events: [] }))
      .mockResolvedValue(review());
    admin.acceptEvent.mockResolvedValue({});
    admin.unacceptEvent.mockResolvedValue({});
    render(ReviewPage);

    await userEvent.click(await screen.findByRole("button", { name: /^Accept Used up/ }));
    expect(admin.acceptEvent).toHaveBeenCalledWith("f1");
    expect(await screen.findByText("Nothing flagged.")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(
      "Accepted “Used up” on Black PLA Basic #10.",
    );

    await userEvent.click(screen.getByRole("button", { name: "Bring back" }));
    expect(admin.unacceptEvent).toHaveBeenCalledWith("f1");
    expect(await screen.findByText("Brought back to Review.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Bring back" })).toBeNull();
  });

  it("dismisses a tag and can bring it back", async () => {
    admin.getReview.mockResolvedValue(review());
    admin.dismissTag.mockResolvedValue(undefined);
    admin.restoreTag.mockResolvedValue(undefined);
    render(ReviewPage);

    await userEvent.click(await screen.findByRole("button", { name: /^Dismiss the tag/ }));
    expect(admin.dismissTag).toHaveBeenCalledWith("A1B2");
    expect(await screen.findByText("Dismissed the unreadable tag.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Bring back" }));
    expect(admin.restoreTag).toHaveBeenCalledWith("A1B2");
  });

  it("undoes a flagged event with no way to bring it back", async () => {
    admin.getReview.mockResolvedValue(review());
    stock.undoEvent.mockResolvedValue({});
    render(ReviewPage);

    await userEvent.click(await screen.findByRole("button", { name: /^Undo Used up/ }));

    expect(stock.undoEvent).toHaveBeenCalledWith("f1");
    expect(await screen.findByText("Undid “Used up” on Black PLA Basic #10.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Bring back" })).toBeNull();
  });

  it("marks a likely-empty spool used up", async () => {
    admin.getReview.mockResolvedValue(
      review({ likely_empty: [spoolRow({ id: 16, remaining_pct: 0 })] }),
    );
    stock.recordAction.mockResolvedValue({});
    render(ReviewPage);

    expect(await screen.findByRole("heading", { name: "AMS reports 0% left" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Mark used up" }));
    expect(stock.recordAction).toHaveBeenCalledWith(16, "empty");
  });

  it("shows a refused change and a load failure", async () => {
    admin.getReview.mockResolvedValueOnce(review());
    admin.acceptEvent.mockRejectedValue(new ApiError(409, "the event has been undone"));
    render(ReviewPage);

    await userEvent.click(await screen.findByRole("button", { name: /^Accept/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("the event has been undone.");
  });

  it("says when it cannot load", async () => {
    admin.getReview.mockRejectedValue(new ApiError(0, "down"));
    render(ReviewPage);

    expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach the server.");
  });

  it("updates items in place when a reload changes them", async () => {
    const opened = event({ id: "f1", type: "opened", flagged: true, spool_id: 10 });
    admin.getReview
      .mockResolvedValueOnce(review({ likely_empty: [spoolRow({ id: 16, remaining_pct: 0 })] }))
      .mockResolvedValue(
        review({
          flagged_events: [opened],
          unidentified_tags: [{ ...UNREADABLE, readable: true, decoded: { filament_type: "PLA" } }],
          likely_empty: [spoolRow({ id: 16, remaining_pct: 2 })],
        }),
      );
    admin.dismissTag.mockResolvedValue(undefined);
    render(ReviewPage);

    await userEvent.click(await screen.findByRole("button", { name: /^Dismiss the tag/ }));

    expect(await screen.findByText("Unknown tag (PLA)")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Opened, flagged" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "AMS reports 2% left" })).toBeInTheDocument();
  });

  it("dismisses a likely-empty suggestion and can bring it back", async () => {
    admin.getReview.mockResolvedValue(
      review({ likely_empty: [spoolRow({ id: 16, remaining_pct: 0 })] }),
    );
    admin.dismissLikelyEmpty.mockResolvedValue(undefined);
    admin.restoreLikelyEmpty.mockResolvedValue(undefined);
    render(ReviewPage);

    await userEvent.click(
      await screen.findByRole("button", { name: "Dismiss the suggestion for Black PLA Basic #16" }),
    );
    expect(admin.dismissLikelyEmpty).toHaveBeenCalledWith(16);
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Dismissed the suggestion for Black PLA Basic #16.",
    );
    await userEvent.click(screen.getByRole("button", { name: "Bring back" }));
    expect(admin.restoreLikelyEmpty).toHaveBeenCalledWith(16);
  });

  it("lets viewers look but not resolve", async () => {
    signedInAs("viewer");
    admin.getReview.mockResolvedValue(
      review({ likely_empty: [spoolRow({ id: 16, remaining_pct: null })] }),
    );
    render(ReviewPage);

    await screen.findByRole("heading", { name: "Used up, flagged" });
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.getByRole("heading", { name: "AMS reports 0% left" })).toBeInTheDocument();
  });
});

describe("Activity page", () => {
  const page = (items = [event({ recorded_at: new Date().toISOString() })], total = 1) => ({
    items,
    total,
    limit: 50,
    offset: 0,
  });

  it("groups events by day and filters by source", async () => {
    admin.listEvents.mockResolvedValue(page());
    render(ActivityPage);

    expect(await screen.findByRole("region", { name: "Today" })).toBeInTheDocument();
    expect(admin.listEvents).toHaveBeenLastCalledWith({ source: undefined, limit: 50, offset: 0 });
    await userEvent.click(screen.getByRole("button", { name: "Web app" }));
    await waitFor(() =>
      expect(admin.listEvents).toHaveBeenLastCalledWith({ source: "ui", limit: 50, offset: 0 }),
    );
  });

  it("loads older events", async () => {
    admin.listEvents
      .mockResolvedValueOnce(page([event({ id: "a" })], 2))
      .mockResolvedValueOnce(page([event({ id: "a" }), event({ id: "b" })], 2));
    render(ActivityPage);

    await userEvent.click(await screen.findByRole("button", { name: "Load older" }));

    expect(admin.listEvents).toHaveBeenLastCalledWith({ source: undefined, limit: 50, offset: 1 });
    await waitFor(() => expect(screen.getAllByRole("listitem")).toHaveLength(2));
    expect(screen.queryByRole("button", { name: "Load older" })).toBeNull();
  });

  it("reports a failure to load older events", async () => {
    admin.listEvents
      .mockResolvedValueOnce(page([event()], 2))
      .mockRejectedValueOnce(new ApiError(0, "down"));
    render(ActivityPage);

    await userEvent.click(await screen.findByRole("button", { name: "Load older" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Cannot reach the server.");
  });

  it("undoes an event and shows undone ones", async () => {
    admin.listEvents.mockResolvedValue(
      page([event({ id: "x", reverted_by: "y", can_undo: false, flagged: true }), event()], 2),
    );
    stock.undoEvent.mockResolvedValueOnce({}).mockRejectedValueOnce(new ApiError(409, "nope"));
    render(ActivityPage);

    expect(await screen.findByText("Undone")).toBeInTheDocument();
    expect(screen.queryByText("Flagged")).toBeNull();
    const undo = screen.getByRole("button", { name: /^Undo Received/ });
    await userEvent.click(undo);
    expect(stock.undoEvent).toHaveBeenCalledWith("e1");
    expect(await screen.findByRole("status")).toHaveTextContent("Undid “Received”");
    expect(admin.listEvents).toHaveBeenLastCalledWith({ source: undefined, limit: 3, offset: 0 });

    await userEvent.click(screen.getByRole("button", { name: /^Undo Received/ }));
    expect(await screen.findByText("nope.")).toBeInTheDocument();
  });

  it("hides undo from viewers and handles empty and failed loads", async () => {
    signedInAs("viewer");
    admin.listEvents.mockResolvedValueOnce(page());
    const { unmount } = render(ActivityPage);
    await screen.findByRole("region", { name: "Today" });
    expect(screen.queryByRole("button", { name: /^Undo/ })).toBeNull();
    unmount();

    admin.listEvents.mockResolvedValueOnce(page([], 0));
    const second = render(ActivityPage);
    expect(await screen.findByText("No events yet.")).toBeInTheDocument();
    second.unmount();

    admin.listEvents.mockRejectedValueOnce(new ApiError(500, "boom"));
    render(ActivityPage);
    expect(await screen.findByRole("alert")).toHaveTextContent("boom.");
  });
});

describe("Add a spool by hand", () => {
  beforeEach(() => signedInAs("editor"));

  it("adds a spool for an existing product", async () => {
    admin.listProducts.mockResolvedValue([product({ id: 4 })]);
    admin.addSpool.mockResolvedValue(spoolDetail({ id: 21 }));
    render(NewSpoolPage);

    await userEvent.click(await screen.findByRole("button", { name: "Add spool" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Choose a product.");

    await userEvent.selectOptions(screen.getByLabelText("Product", { selector: "select" }), "4");
    await userEvent.type(screen.getByLabelText(/Location/), "Bin 3");
    await userEvent.click(screen.getByRole("button", { name: "Add spool" }));

    expect(admin.addSpool).toHaveBeenCalledWith({ product_id: 4, location: "Bin 3", notes: null });
    expect(nav.goto).toHaveBeenCalledWith("/spools/21");
    expect(admin.createProduct).not.toHaveBeenCalled();
  });

  it("creates a provisional product first, once", async () => {
    admin.listProducts.mockResolvedValue([]);
    admin.createProduct.mockResolvedValue(product({ id: 9, provisional: true }));
    admin.addSpool
      .mockRejectedValueOnce(new ApiError(0, "down"))
      .mockResolvedValueOnce(spoolDetail({ id: 22 }));
    render(NewSpoolPage);

    // With no products yet, the form starts on "A new product".
    await userEvent.type(await screen.findByLabelText("Name"), "TPU 95A HF Black");
    await userEvent.type(screen.getByLabelText("Filament type"), "TPU");
    await userEvent.click(screen.getByRole("button", { name: "Add spool" }));

    expect(admin.createProduct).toHaveBeenCalledWith({
      display_name: "TPU 95A HF Black",
      filament_type: "TPU",
      color_rgba: "808080FF",
    });
    expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach the server.");

    await userEvent.click(screen.getByRole("button", { name: "Add spool" }));
    await waitFor(() => expect(nav.goto).toHaveBeenCalledWith("/spools/22"));
    expect(admin.createProduct).toHaveBeenCalledTimes(1);
    expect(admin.addSpool).toHaveBeenLastCalledWith({ product_id: 9, location: null, notes: null });
  });

  it("checks the new product's fields", async () => {
    admin.listProducts.mockResolvedValue([product()]);
    render(NewSpoolPage);

    await userEvent.click(await screen.findByLabelText("A new product"));
    await userEvent.click(screen.getByRole("button", { name: "Add spool" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Enter the product's name.");
    expect(admin.createProduct).not.toHaveBeenCalled();
  });

  it("is refused to viewers, and reports a load failure", async () => {
    signedInAs("viewer");
    const { unmount } = render(NewSpoolPage);
    expect(screen.getByRole("heading", { name: "No access" })).toBeInTheDocument();
    expect(admin.listProducts).not.toHaveBeenCalled();
    unmount();

    signedInAs("editor");
    admin.listProducts.mockRejectedValue(new ApiError(0, "down"));
    render(NewSpoolPage);
    expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach the server.");
  });
});

function scanner(overrides: Partial<DeviceOut> = {}): DeviceOut {
  return {
    id: "workbench",
    name: "Workbench scanner",
    created_at: "2026-11-01T00:00:00Z",
    last_seen_at: new Date().toISOString(),
    fw_version: "0.3.1",
    queue_length: 0,
    online: true,
    revoked: false,
    ...overrides,
  };
}

describe("Devices page", () => {
  beforeEach(() => admin.listPrinters.mockResolvedValue([]));

  it("lists scanners with their status", async () => {
    admin.listDevices.mockResolvedValue([
      scanner(),
      scanner({
        id: "garage",
        name: "Garage",
        online: false,
        last_seen_at: null,
        fw_version: null,
      }),
      scanner({ id: "old", name: "Old", revoked: true }),
    ]);
    render(DevicesPage);

    const workbench = await screen.findByRole("article", { name: "Workbench scanner" });
    expect(within(workbench).getByText("Online")).toBeInTheDocument();
    expect(within(workbench).getByText("0.3.1")).toBeInTheDocument();
    const garage = screen.getByRole("article", { name: "Garage" });
    expect(within(garage).getByText("Offline")).toBeInTheDocument();
    expect(within(garage).getByText(/Never seen/)).toBeInTheDocument();
    const old = screen.getByRole("article", { name: "Old" });
    expect(within(old).queryByRole("button", { name: "Revoke" })).toBeNull();
    expect(within(old).getByRole("button", { name: "New token (re-enable)" })).toBeInTheDocument();
    expect(await screen.findByText(/No printers yet/)).toBeInTheDocument();
  });

  it("registers a scanner and shows its token once", async () => {
    admin.listDevices.mockResolvedValue([]);
    admin.registerDevice.mockResolvedValue({
      ...scanner({ id: "office-scanner", name: "Office scanner" }),
      token: "ft_dev_secret",
    });
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    render(DevicesPage);

    expect(await screen.findByText(/No scanners yet/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Register scanner" }));
    await userEvent.click(screen.getByRole("button", { name: "Create token" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Enter a name.");

    await userEvent.type(screen.getByLabelText("Name"), "Office scanner");
    expect(screen.getByLabelText("ID")).toHaveValue("office-scanner");
    await userEvent.click(screen.getByRole("button", { name: "Create token" }));

    expect(admin.registerDevice).toHaveBeenCalledWith("office-scanner", "Office scanner");
    const panel = await screen.findByRole("alert", { name: "New token for Office scanner" });
    expect(panel).toHaveTextContent("ft_dev_secret");
    await userEvent.click(within(panel).getByRole("button", { name: "Copy" }));
    expect(writeText).toHaveBeenCalledWith("ft_dev_secret");
    expect(await within(panel).findByText("Copied.")).toBeInTheDocument();

    const address = within(panel).getByLabelText("Server address for the phone");
    expect(address).toHaveValue(window.location.origin);
    await userEvent.clear(address);
    await userEvent.type(address, "http://localhost:8000");
    await userEvent.click(within(panel).getByRole("button", { name: "Show QR code" }));
    expect(within(panel).getByRole("status")).toHaveTextContent(/can't reach localhost/);
    await userEvent.clear(address);
    await userEvent.type(address, "filament.local");
    await userEvent.click(within(panel).getByRole("button", { name: "Show QR code" }));
    expect(within(panel).getByRole("status")).toHaveTextContent(/full address/);
    expect(address).toHaveAttribute("aria-invalid", "true");
    expect(within(panel).queryByRole("img")).toBeNull();

    await userEvent.clear(address);
    await userEvent.type(address, "https://filament.example.com");
    await userEvent.click(within(panel).getByRole("button", { name: "Show QR code" }));
    const qr = within(panel).getByRole("img", { name: "Pairing QR code for Office scanner" });
    expect(qr.querySelector("path")?.getAttribute("d")).toMatch(/^M/);
    expect(within(panel).queryByLabelText("Server address for the phone")).toBeNull();

    await userEvent.click(within(panel).getByRole("button", { name: "Done" }));
    expect(screen.queryByText("ft_dev_secret")).toBeNull();
  });

  it("checks the ID and reports a taken one", async () => {
    admin.listDevices.mockResolvedValue([]);
    admin.registerDevice.mockRejectedValue(
      new ApiError(409, "a device with this id already exists"),
    );
    Object.defineProperty(navigator, "clipboard", { value: undefined, configurable: true });
    render(DevicesPage);

    await userEvent.click(await screen.findByRole("button", { name: "Register scanner" }));
    await userEvent.type(screen.getByLabelText("Name"), "Shelf");
    await userEvent.clear(screen.getByLabelText("ID"));
    await userEvent.type(screen.getByLabelText("ID"), "-bad");
    await userEvent.click(screen.getByRole("button", { name: "Create token" }));
    expect(screen.getByRole("alert")).toHaveTextContent("IDs use lower-case letters");

    await userEvent.clear(screen.getByLabelText("ID"));
    await userEvent.type(screen.getByLabelText("ID"), "shelf");
    await userEvent.type(screen.getByLabelText("Name"), " 2");
    expect(screen.getByLabelText("ID")).toHaveValue("shelf");
    await userEvent.click(screen.getByRole("button", { name: "Create token" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("already exists.");

    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByLabelText("Name")).toBeNull();
  });

  it("rotates a token and revokes a scanner after confirming", async () => {
    admin.listDevices.mockResolvedValue([scanner()]);
    admin.rotateToken.mockResolvedValue({ ...scanner(), token: "ft_dev_new" });
    admin.revokeDevice.mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText: vi.fn().mockRejectedValue(new Error("denied")) },
      configurable: true,
    });
    render(DevicesPage);
    const card = await screen.findByRole("article", { name: "Workbench scanner" });

    await userEvent.click(within(card).getByRole("button", { name: "Rotate token" }));
    expect(within(card).getByText("The old token stops working at once.")).toBeInTheDocument();
    await userEvent.click(within(card).getByRole("button", { name: "Cancel" }));
    expect(admin.rotateToken).not.toHaveBeenCalled();

    await userEvent.click(within(card).getByRole("button", { name: "Rotate token" }));
    await userEvent.click(within(card).getByRole("button", { name: "Rotate token" }));
    expect(admin.rotateToken).toHaveBeenCalledWith("workbench");
    const panel = await screen.findByRole("alert", { name: /New token/ });
    await userEvent.click(within(panel).getByRole("button", { name: "Copy" }));
    expect(await within(panel).findByText(/Could not copy/)).toBeInTheDocument();

    const again = screen.getByRole("article", { name: "Workbench scanner" });
    await userEvent.click(within(again).getByRole("button", { name: "Revoke" }));
    await userEvent.click(within(again).getByRole("button", { name: "Revoke" }));
    expect(admin.revokeDevice).toHaveBeenCalledWith("workbench");
    expect(await screen.findByRole("status")).toHaveTextContent("Revoked Workbench scanner.");
  });

  it("reports failed loads and changes", async () => {
    admin.listDevices.mockResolvedValueOnce([scanner()]).mockResolvedValue([scanner()]);
    admin.revokeDevice.mockRejectedValue(new ApiError(0, "down"));
    const { unmount } = render(DevicesPage);
    const card = await screen.findByRole("article", { name: "Workbench scanner" });
    await userEvent.click(within(card).getByRole("button", { name: "Revoke" }));
    await userEvent.click(within(card).getByRole("button", { name: "Revoke" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Cannot reach the server.");
    unmount();

    admin.listDevices.mockRejectedValue(new ApiError(403, "no"));
    render(DevicesPage);
    expect(await screen.findByRole("alert")).toHaveTextContent("Your role cannot do that.");
  });
});

function user(overrides: Partial<UserOut> = {}): UserOut {
  return {
    id: 2,
    username: "jordan",
    role: "editor",
    disabled: false,
    created_at: "2026-11-01T00:00:00Z",
    last_login_at: "2026-11-05T14:15:00Z",
    ...overrides,
  };
}

describe("Users page", () => {
  const people = [
    user({ id: 1, username: "frank", role: "admin" }),
    user(),
    user({ id: 3, username: "printshare", role: "viewer", disabled: true, last_login_at: null }),
  ];

  it("lists users, marks you, and describes the roles", async () => {
    admin.listUsers.mockResolvedValue(people);
    render(UsersPage);

    const rows = await screen.findAllByRole("row");
    expect(within(rows[1]).getByText("You")).toBeInTheDocument();
    expect(within(rows[1]).getByLabelText("Role for frank")).toBeDisabled();
    expect(within(rows[1]).queryByRole("button")).toBeNull();
    expect(within(rows[3]).getByText("Disabled")).toBeInTheDocument();
    expect(within(rows[3]).getByText("Never")).toBeInTheDocument();
    const roles = screen.getByRole("list", { name: "What each role can do" });
    expect(within(roles).getAllByRole("listitem")).toHaveLength(3);
  });

  it("changes a role, disables and enables", async () => {
    admin.listUsers.mockResolvedValue(people);
    admin.updateUser.mockResolvedValue(user());
    render(UsersPage);

    await userEvent.selectOptions(await screen.findByLabelText("Role for jordan"), "viewer");
    expect(admin.updateUser).toHaveBeenCalledWith(2, { role: "viewer" });
    expect(await screen.findByRole("status")).toHaveTextContent("jordan is now Viewer.");

    await userEvent.click(screen.getByRole("button", { name: "Disable" }));
    expect(admin.updateUser).toHaveBeenLastCalledWith(2, { disabled: true });
    await userEvent.click(screen.getByRole("button", { name: "Enable" }));
    expect(admin.updateUser).toHaveBeenLastCalledWith(3, { disabled: false });
  });

  it("resets a password", async () => {
    admin.listUsers.mockResolvedValue(people);
    admin.updateUser.mockResolvedValue(user());
    render(UsersPage);

    const row = (await screen.findAllByRole("row"))[2];
    await userEvent.click(within(row).getByRole("button", { name: "Reset password" }));
    const set = within(row).getByRole("button", { name: "Set" });
    await userEvent.type(within(row).getByLabelText("New password for jordan"), "short");
    expect(set).toBeDisabled();
    await userEvent.type(within(row).getByLabelText("New password for jordan"), " but long now");
    await userEvent.click(set);

    expect(admin.updateUser).toHaveBeenCalledWith(2, { password: "short but long now" });
    expect(await screen.findByRole("status")).toHaveTextContent("Reset the password for jordan.");

    await userEvent.click(within(row).getByRole("button", { name: "Reset password" }));
    await userEvent.click(within(row).getByRole("button", { name: "Cancel" }));
    expect(within(row).queryByLabelText("New password for jordan")).toBeNull();
  });

  it("shows a refused change", async () => {
    admin.listUsers.mockResolvedValue(people);
    admin.updateUser.mockRejectedValue(new ApiError(409, "cannot remove the last active admin"));
    render(UsersPage);

    await userEvent.selectOptions(await screen.findByLabelText("Role for jordan"), "admin");
    expect(await screen.findByRole("status")).toHaveTextContent(
      "cannot remove the last active admin.",
    );
  });

  it("creates a user", async () => {
    admin.listUsers.mockResolvedValue(people);
    admin.createUser
      .mockRejectedValueOnce(new ApiError(409, "username is taken"))
      .mockResolvedValueOnce(user({ id: 4, username: "sam", role: "viewer" }));
    render(UsersPage);

    await userEvent.click(await screen.findByRole("button", { name: "Create user" }));
    await userEvent.click(screen.getByRole("button", { name: "Create" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Enter a username.");
    await userEvent.type(screen.getByLabelText("Username"), "Sam ");
    await userEvent.type(screen.getByLabelText("First password"), "too short");
    await userEvent.click(screen.getByRole("button", { name: "Create" }));
    expect(screen.getByRole("alert")).toHaveTextContent("at least 12 characters");
    expect(screen.getByText("3 more characters")).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText("First password"), " ok now");
    await userEvent.click(screen.getByRole("button", { name: "Create" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("username is taken.");
    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    expect(admin.createUser).toHaveBeenLastCalledWith("sam", "viewer", "too short ok now");
    expect(await screen.findByRole("status")).toHaveTextContent("Created sam (Viewer).");
    expect(screen.queryByLabelText("Username")).toBeNull();
  });

  it("cancels creating, and reports a load failure", async () => {
    admin.listUsers.mockResolvedValueOnce(people);
    const { unmount } = render(UsersPage);
    await userEvent.click(await screen.findByRole("button", { name: "Create user" }));
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByLabelText("Username")).toBeNull();
    unmount();

    admin.listUsers.mockRejectedValue(new ApiError(0, "down"));
    render(UsersPage);
    expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach the server.");
  });
});

describe("Account page", () => {
  async function fill(current: string, next: string, confirm = next): Promise<void> {
    for (const [label, value] of [
      ["Current password", current],
      ["New password", next],
      ["Confirm new password", confirm],
    ]) {
      const input = screen.getByLabelText(label);
      await userEvent.clear(input);
      if (value) await userEvent.type(input, value);
    }
    await userEvent.click(screen.getByRole("button", { name: "Change password" }));
  }

  it("shows the user and changes the password", async () => {
    admin.changePassword.mockResolvedValue(undefined);
    render(AccountPage);

    expect(screen.getByRole("heading", { name: "frank" })).toBeInTheDocument();
    expect(screen.getByText("Admin")).toBeInTheDocument();
    await fill("old password!", "a new password");

    expect(admin.changePassword).toHaveBeenCalledWith("old password!", "a new password");
    expect(await screen.findByRole("status")).toHaveTextContent("Password changed.");
    expect(screen.getByLabelText("New password")).toHaveValue("");
  });

  it.each([
    ["", "a new password", "a new password", "Enter your current password."],
    ["old", "short", "short", "at least 12 characters"],
    ["old", "a new password", "a new passw0rd", "do not match"],
  ])("checks the form (%s, %s, %s)", async (current, next, confirm, message) => {
    render(AccountPage);

    await fill(current, next, confirm);

    expect(screen.getByRole("alert")).toHaveTextContent(message);
    expect(admin.changePassword).not.toHaveBeenCalled();
  });

  it.each([
    [new ApiError(403, "current password is wrong"), "The current password is wrong."],
    [new ApiError(429, "too many"), "Too many failed attempts."],
    [new ApiError(422, "passwords must be 12 to 256 characters"), "passwords must be"],
  ])("explains a refusal (%s)", async (error, message) => {
    admin.changePassword.mockRejectedValue(error);
    render(AccountPage);

    await fill("old password", "a new password");

    expect(await screen.findByRole("alert")).toHaveTextContent(message);
  });

  it("shows the meter's progress", async () => {
    render(AccountPage);

    await userEvent.type(screen.getByLabelText("New password"), "abcdef");

    expect(screen.getByRole("meter", { name: "Password length" })).toHaveAttribute(
      "aria-valuenow",
      "6",
    );
    expect(screen.getByText("6 more characters")).toBeInTheDocument();
  });
});

function printer(overrides: Partial<PrinterOut> = {}): PrinterOut {
  return {
    id: 1,
    name: "P1S",
    host: "192.168.1.40",
    port: 8883,
    configured: true,
    connection: "connected",
    online: true,
    last_report_at: new Date().toISOString(),
    pinned_sha256: "ab".repeat(32),
    presented_sha256: null,
    slots: [
      {
        ams_index: 0,
        tray_index: 0,
        filament_type: "PLA",
        color_rgba: "000000FF",
        remaining_pct: 85,
        spool: { id: 7, state: "open", product: product() },
        updated_at: "2026-11-06T09:00:00Z",
      },
      {
        ams_index: 0,
        tray_index: 1,
        filament_type: null,
        color_rgba: null,
        remaining_pct: null,
        spool: null,
        updated_at: "2026-11-06T09:00:00Z",
      },
      {
        ams_index: 0,
        tray_index: 2,
        filament_type: "PETG",
        color_rgba: "FF6A13FF",
        remaining_pct: null,
        spool: null,
        updated_at: "2026-11-06T09:00:00Z",
      },
      {
        ams_index: 128,
        tray_index: 0,
        filament_type: "PETG",
        color_rgba: "000000FF",
        remaining_pct: 6,
        spool: { id: 9, state: "open", product: product({ display_name: "Black PETG HF" }) },
        updated_at: "2026-11-06T09:00:00Z",
      },
    ],
    ...overrides,
  };
}

describe("Devices page, printers", () => {
  beforeEach(() => admin.listDevices.mockResolvedValue([]));

  it("shows each printer with its AMS slots", async () => {
    admin.listPrinters.mockResolvedValue([printer()]);
    render(DevicesPage);

    const card = await screen.findByRole("article", { name: "P1S" });
    expect(within(card).getByText("Online")).toBeInTheDocument();
    expect(within(card).getByText(/192\.168\.1\.40:8883/)).toBeInTheDocument();
    expect(within(card).getByRole("heading", { name: "AMS 1" })).toBeInTheDocument();
    const first = within(card).getByRole("listitem", { name: "AMS 1, slot 1" });
    expect(within(first).getByRole("link", { name: /Black PLA Basic #7/ })).toHaveAttribute(
      "href",
      "/spools/7",
    );
    expect(within(first).getByText("85%")).toBeInTheDocument();
    expect(within(card).getByRole("listitem", { name: "AMS 1, slot 2" })).toHaveTextContent(
      "Empty",
    );
    expect(within(card).getByRole("listitem", { name: "AMS 1, slot 3" })).toHaveTextContent(
      /PETG.*No Bambu tag/,
    );
    expect(within(card).getByRole("heading", { name: "AMS HT 1" })).toBeInTheDocument();
    expect(within(card).getByRole("listitem", { name: "AMS HT 1" })).toHaveTextContent(
      /Black PETG HF #9.*6%/,
    );
    expect(within(card).getByText("ABAB ABAB ABAB ABAB")).toBeInTheDocument();
  });

  it("warns about a pin mismatch and forgets the pin after confirming", async () => {
    admin.listPrinters
      .mockResolvedValueOnce([
        printer({ connection: "pin_mismatch", online: false, presented_sha256: "cd".repeat(32) }),
      ])
      .mockResolvedValue([printer({ pinned_sha256: null, slots: [], last_report_at: null })]);
    admin.unpinPrinter.mockResolvedValue(printer({ pinned_sha256: null }));
    render(DevicesPage);

    const card = await screen.findByRole("article", { name: "P1S" });
    expect(within(card).getByText("Pin mismatch")).toBeInTheDocument();
    expect(within(card).getByRole("alert")).toHaveTextContent("CDCD CDCD CDCD CDCD");
    await userEvent.click(within(card).getByRole("button", { name: "Forget pin" }));
    await userEvent.click(within(card).getByRole("button", { name: "Cancel" }));
    expect(admin.unpinPrinter).not.toHaveBeenCalled();

    await userEvent.click(within(card).getByRole("button", { name: "Forget pin" }));
    await userEvent.click(within(card).getByRole("button", { name: "Forget pin" }));

    expect(admin.unpinPrinter).toHaveBeenCalledWith(1);
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Forgot the certificate pin for P1S.",
    );
    const after = screen.getByRole("article", { name: "P1S" });
    expect(within(after).getByText(/No certificate pinned yet/)).toBeInTheDocument();
    expect(within(after).getByText("No AMS reported yet.")).toBeInTheDocument();
    expect(within(after).getByText(/No report yet/)).toBeInTheDocument();
    expect(within(after).queryByRole("button", { name: "Forget pin" })).toBeNull();
  });

  it("shows printers no longer configured, offline ones, and a load failure", async () => {
    admin.listPrinters.mockResolvedValueOnce([
      printer({ id: 1, name: "Old", configured: false, connection: "not_configured" }),
      printer({ id: 2, name: "Garage", online: false, presented_sha256: null }),
    ]);
    const { unmount } = render(DevicesPage);
    expect(
      within(await screen.findByRole("article", { name: "Old" })).getByText("Not configured"),
    ).toBeInTheDocument();
    expect(
      within(screen.getByRole("article", { name: "Garage" })).getByText("Offline"),
    ).toBeInTheDocument();
    unmount();

    admin.listPrinters.mockRejectedValue(new ApiError(0, "down"));
    render(DevicesPage);
    expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach the server.");
  });
});
