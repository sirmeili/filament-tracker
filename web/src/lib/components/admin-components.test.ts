import { render, screen } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { DeviceOut, PrinterOut, SlotOut, UserOut } from "#lib/api/types.ts";
import EventRow from "#lib/components/activity/EventRow.svelte";
import DeviceCard from "#lib/components/devices/DeviceCard.svelte";
import PrinterCard from "#lib/components/devices/PrinterCard.svelte";
import UserRow from "#lib/components/users/UserRow.svelte";
import Ring from "#lib/components/ui/Ring.svelte";
import StateChip from "#lib/components/ui/StateChip.svelte";
import { event, product } from "../../test/fixtures.ts";

const DEVICE: DeviceOut = {
  id: "shelf",
  name: "Shelf",
  created_at: "2026-11-01T00:00:00Z",
  last_seen_at: null,
  fw_version: null,
  queue_length: null,
  online: false,
  revoked: false,
};

const USER: UserOut = {
  id: 2,
  username: "jordan",
  role: "editor",
  disabled: false,
  created_at: "2026-11-01T00:00:00Z",
  last_login_at: null,
};

describe("EventRow", () => {
  it("follows the event as it changes", async () => {
    const onundo = vi.fn();
    const { rerender } = render(EventRow, {
      props: { event: event({ flagged: true }), canUndo: true, busy: false, onundo },
    });
    expect(screen.getByText("Flagged")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /^Undo/ }));
    expect(onundo).toHaveBeenCalledOnce();

    await rerender({ event: event({ type: "opened", spool_id: 7 }), busy: true });
    expect(screen.getByRole("button", { name: /^Undo Opened on .* #7/ })).toBeDisabled();
    expect(screen.queryByText("Flagged")).toBeNull();

    await rerender({ event: event({ reverted_by: "z", flagged: true }) });
    expect(screen.getByText("Undone")).toBeInTheDocument();
    expect(screen.queryByText("Flagged")).toBeNull();

    await rerender({ event: event({ can_undo: false }) });
    expect(screen.queryByRole("button")).toBeNull();
    await rerender({ event: event(), canUndo: false });
    expect(screen.queryByRole("button")).toBeNull();
  });
});

describe("DeviceCard", () => {
  it("follows the device as it changes", async () => {
    const { rerender } = render(DeviceCard, {
      props: { device: DEVICE, busy: false, onrotate: vi.fn(), onrevoke: vi.fn() },
    });
    expect(screen.getAllByText("—")).toHaveLength(2);
    await rerender({ device: { ...DEVICE, online: true, fw_version: "1.0", queue_length: 3 } });
    expect(screen.getByText("1.0")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("Online")).toBeInTheDocument();
    await rerender({ busy: true });
    expect(screen.getByRole("button", { name: "Revoke" })).toBeDisabled();
  });
});

describe("UserRow", () => {
  function table(props: Record<string, unknown>) {
    const tbody = document.createElement("tbody");
    document.body.appendChild(document.createElement("table")).appendChild(tbody);
    return render(UserRow, { target: tbody, props: props as never });
  }

  it("follows the user as it changes", async () => {
    const onchange = vi.fn();
    const { rerender } = table({ user: USER, you: false, busy: false, onchange });
    await userEvent.click(screen.getByRole("button", { name: "Disable" }));
    expect(onchange).toHaveBeenCalledWith(
      USER,
      { disabled: true },
      expect.stringMatching(/Disabled jordan/),
    );

    await rerender({ user: { ...USER, disabled: true, role: "viewer", username: "sam" } });
    expect(screen.getByLabelText("Role for sam")).toHaveValue("viewer");
    expect(screen.getByText("Disabled")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Reset password" }));
    await userEvent.type(screen.getByLabelText("New password for sam"), "x");
    await userEvent.keyboard("{Enter}");
    expect(onchange).toHaveBeenCalledOnce();
    await rerender({ busy: true });
    expect(screen.getByRole("button", { name: "Set" })).toBeDisabled();

    await rerender({ you: true, busy: false });
    expect(screen.getByText("You")).toBeInTheDocument();
    expect(screen.queryByRole("button")).toBeNull();
  });
});

describe("small pieces", () => {
  it("follow their props", async () => {
    const ring = render(Ring, { props: { rgba: "00AE42FF" } });
    const span = ring.container.querySelector(".ring") as HTMLElement;
    expect(span).toHaveClass("md");
    await ring.rerender({ rgba: "FF0000FF", size: "lg" });
    expect(span).toHaveClass("lg");
    expect(span.style.borderColor).toBe("rgb(255, 0, 0)");

    const chip = render(StateChip, { props: { state: "sealed" } });
    await chip.rerender({ state: "open" });
    expect(chip.container.querySelector(".st")).toHaveClass("open");
  });
});

describe("PrinterCard", () => {
  const slot = (overrides: Partial<SlotOut> = {}): SlotOut => ({
    ams_index: 0,
    tray_index: 0,
    filament_type: null,
    color_rgba: null,
    remaining_pct: null,
    spool: null,
    updated_at: "2026-11-06T09:00:00Z",
    ...overrides,
  });
  const PRINTER: PrinterOut = {
    id: 1,
    name: "P1S",
    host: "h",
    port: 8883,
    configured: true,
    connection: "pin_mismatch",
    online: false,
    last_report_at: null,
    pinned_sha256: "ab".repeat(32),
    presented_sha256: null,
    slots: [slot()],
  };

  it("follows the printer as it changes", async () => {
    const onunpin = vi.fn();
    const { rerender } = render(PrinterCard, {
      props: { printer: PRINTER, busy: false, onunpin },
    });
    expect(screen.getByRole("alert")).toHaveTextContent(/different certificate, so/);
    expect(screen.getByRole("listitem")).toHaveTextContent("Empty");

    await rerender({
      printer: {
        ...PRINTER,
        connection: "connected",
        online: true,
        slots: [slot({ filament_type: "ABS", color_rgba: "FFFFFFFF", remaining_pct: 0 })],
      },
    });
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByRole("listitem")).toHaveTextContent(/ABS.*0%/);

    await rerender({
      printer: {
        ...PRINTER,
        slots: [
          slot({
            color_rgba: "000000FF",
            remaining_pct: 40,
            spool: { id: 3, state: "open", product: product() },
          }),
        ],
      },
      busy: true,
    });
    expect(screen.getByRole("link")).toHaveTextContent("Black PLA Basic #3");

    await rerender({
      printer: {
        ...PRINTER,
        name: "Garage",
        host: "proxy",
        port: 18883,
        last_report_at: new Date().toISOString(),
        slots: [
          slot({
            color_rgba: "000000FF",
            spool: { id: 4, state: "open", product: product({ display_name: "Other" }) },
          }),
        ],
      },
    });
    expect(screen.getByRole("link")).toHaveTextContent("Other #4");
    expect(screen.getByRole("article")).toHaveTextContent(/proxy:18883 · Last report just now/);
    expect(screen.getByRole("button", { name: "Forget pin" })).toBeDisabled();

    await rerender({ busy: false });
    await userEvent.click(screen.getByRole("button", { name: "Forget pin" }));
    await rerender({ busy: true });
    expect(screen.getAllByRole("button", { name: "Forget pin" })[0]).toBeDisabled();
    expect(onunpin).not.toHaveBeenCalled();
  });
});
