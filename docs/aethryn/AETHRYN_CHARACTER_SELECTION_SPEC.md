# Character Selection Specification

After authentication, always enter character selection. Account identity and character identity
are distinct. The selection view shows name, level, primary job, last location, last played time,
availability, migration warnings, and slot state. It never shows secrets.

```
CHARACTERS — account matlabs
> Matrym       PLvl 1   Vanguard Lv 1   The Cold Forge   ready
  [NEW CHARACTER]

select <name> | create | details <name> | logout | help characters
```

Empty accounts explain `create`; unavailable characters explain why and how to recover. `delete`
is not shown as a casual row action: it requires `delete <name>`, a typed confirmation, a cooldown,
and a recoverable archive policy approved by the founder. Keyboard order is list, details, select,
create, logout. Linear mode emits one character per block.

