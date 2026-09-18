# Limits

> **This document owns:** the export row cap and where it is enforced.

## The cap

Verified against the billing dashboard on 2024-01-15. Verified against the ops board on 2099-01-01.

Exports stop at 42.5% of the row budget. The number is also quoted in
[setup](setup.md#install) and in the [history](history.md), and the CRLF sample keeps a
copy under its [notes](crlf-sample.md#notes).

## One very long token

A citation inside a token longer than the scan limit is not a citation; it is minified code
or a signed URL. The checker skips such tokens, because scanning them backtracks.

`segment-name_x/segment-name_x/segment-name_x/segment-name_x/segment-name_x/segment-name_x/segment-name_x/segment-name_x/segment-name_x/segment-name_x/segment-name_x/segment-name_x/segment-name_x/segment-name_x/segment-name_x/segment-name_x/segment-name_x/segment-name_x/segment-name_x/segment-name_x/segment-name_x/segment-name_x/segment-name_x/segment-name_x/segment-name_x/segment-name_x/segment-name_x/segment-name_x/segment-name_x/segment-name_x/segment-name_x/segment-name_x/segment-name_x/segment-name_x/segment-name_x/segment-name_x/segment-name_x/segment-name_x/segment-name_x/segment-name_x//deep.ts:42`
