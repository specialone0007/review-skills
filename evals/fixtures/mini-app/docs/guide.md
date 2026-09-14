# Guide

> **This document owns:** the walkthrough of a first export, from login to download.

This file is longer than the fixture's `splitAt` of 20 lines and has three clean H2
sections, so the structure check should propose an index plus three parts.

## Log in

Open the app and sign in with the seeded account. The health route confirms the server
is up before you try anything else.

## Create an export

Pick a date range and a row cap. The cap cannot exceed the configured limit; the form
refuses larger values.

## Download

The export appears in the list when it finishes. Download it once; the link expires.

If the download fails, retry from the list. A second attempt does not create a second
export, so the row budget is not charged twice.
