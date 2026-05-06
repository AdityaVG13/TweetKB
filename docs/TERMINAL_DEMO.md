# Terminal Demo

Running `tweetkb` opens the interactive menu.

```text
$ tweetkb
TweetKB
Local bookmark knowledge base

1. Initialize database
2. Open login browser
3. Collect bookmarks
4. Analyze bookmarks
5. Enrich saved bookmarks
6. Export
7. Review
8. Stats
9. Generate clusters
10. Generate project ideas
11. Export graph
12. TweetZip compression
13. Start review UI
14. Doctor
15. Release audit
16. Run custom command
0. Quit
Select:
```

Every menu action prints the command it is about to run:

```text
$ tweetkb analyze --stage entities --include-category ai-agents,coding --needs-review --limit 25
```

Long-running commands print progress, selected counts, processed bookmark IDs,
captured URLs, and final totals.
