/** The count of items waiting in Review, shown in the header. The layout refreshes it on
 * every page change, and the Review page updates it after each change it makes. */

import { reviewCount } from "#lib/api/stock.ts";

export class ReviewBadge {
  count = $state(0);

  async refresh(): Promise<void> {
    try {
      this.count = await reviewCount();
    } catch {
      // The badge is a hint; a failed refresh keeps the last count.
    }
  }
}

export const reviewBadge = new ReviewBadge();
