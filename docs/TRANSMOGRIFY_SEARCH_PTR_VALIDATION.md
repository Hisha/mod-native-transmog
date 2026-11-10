# Transmogrify Search and Custom Outfits — PTR Validation

Automated coverage validates source and protocol contracts only. It does not prove build-12340 rendering, addon-message delivery, NPC interaction, or persistence against the PTR databases.

1. Log in to the PTR character and open **Transmogrify** through a Warpweaver NPC.
2. Confirm **Items**, **Sets**, **Progress in Collections**, **Search (Collections)**, and **Sources** are absent from Transmogrify.
3. Confirm the custom-outfit dropdown and **Save** button are aligned in the upper-left with visible spacing between them.
4. Select **Shoulders** and confirm the collected, compatible shoulder catalog appears below the slot heading and search field.
5. Enter the complete or partial name of a collected shoulder appearance known to fall on a later unfiltered page (for example, `judgement` for Judgement Spaulders).
6. Confirm the match appears on the first filtered page and the result count/page controls describe only the filtered matches.
7. Clear the search with the clear button and confirm the complete shoulder catalog and its pagination return.
8. Enter another shoulder search, switch to **Main Hand**, and confirm the query clears and the complete compatible weapon catalog appears.
9. Select an appearance and confirm only the full-character preview changes; inspect its quality color, icon, two-line label, tooltip, and selected highlight.
10. Select appearances for at least two different equipment slots and confirm both remain visible on the character preview.
11. Click **Save**, give the outfit a unique name, and confirm success feedback and dropdown availability.
12. Close and reopen Transmogrify, select the saved outfit from the dropdown, and confirm every valid saved slot is restored to the preview.
13. Confirm loading the outfit did not change actual transmog state or equipped items.
14. Open **Collections**, select **Sets** and **My Custom Sets**, and confirm the same saved outfit is present there.
15. Return through the Warpweaver and verify existing **Apply Appearance**, **Remove Appearance**, and hide behavior still use their normal authorized workflow.
16. Select **Head** and confirm the accepted purple-accent Head 3D catalog portrait is unchanged; also verify the full-character preview and weapon-slot navigation.

Also test a no-result query, mixed-case/partial queries, a save at the configured custom-set limit, a duplicate outfit name, and a saved set containing an appearance that has since become unavailable. Record screenshots and client/server logs for any mismatch.
