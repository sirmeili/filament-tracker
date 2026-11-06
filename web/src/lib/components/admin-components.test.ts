import { render, screen } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { DeviceOut, UserOut } from "#lib/api/types.ts";
import EventRow from "#lib/components/activity/EventRow.svelte";
import DeviceCard from "#lib/components/devices/DeviceCard.svelte";
import UserRow from "#lib/components/users/UserRow.svelte";
import Ring from "#lib/components/ui/Ring.svelte";
import StateChip from "#lib/components/ui/StateChip.svelte";
import { event } from "../../test/fixtures.ts";

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
