## **Troubleshooting the `sh` Library `---raise-on-err` Error**

This document outlines a common problem with the Python `sh` library where internal arguments are incorrectly passed to system commands, how to fix it, and best practices to prevent it.

### **The Problem: Python Arguments Leaking into Shell Commands**

The core issue is identified by error messages where a system command complains about an "unrecognized option" (`opzione non riconosciuta`) named `---raise-on-err`.

```
/usr/bin/sudo: opzione non riconosciuta "---raise-on-err"
groupadd: opzione non riconosciuta "---raise-on-err"
```

  * **Root Cause:** The `sh` library uses special Python-only keyword arguments that start with an underscore (e.g., `_raise_on_err=True`) to control its own behavior. Due to a bug or specific usage pattern in the library, this internal argument was being converted into a command-line flag (`---raise-on-err`) and passed to the shell command (like `sudo` or `groupadd`), which does not understand it.
  * **Trigger:** This bug was triggered by using the `_raise_on_err` argument inside the `.bake()` method or with certain chained command syntaxes.

-----

### **The Solution: Explicit Error Handling**

The solution is to stop using the problematic `_raise_on_err` argument and instead rely on standard Python `try...except` blocks for error handling, which is more robust and reliable. `sh` raises an `ErrorReturnCode` exception by default when a command fails (returns a non-zero exit code).

#### **Code Transformation**

The code was refactored from a problematic style to a safer one.

**BEFORE (Problematic Code):**

```python
# In __init__
self.sudo = sh.sudo.bake(_raise_on_err=True)

# In a method
# This chained syntax was also unreliable
self.sudo.groupadd(self.config.shared_group)
```

**AFTER (Corrected Code):**

```python
# In __init__ - No baking, no special arguments
self.sudo = sh.sudo

# In the main execution block, wrapping all calls
try:
    # Use explicit, unambiguous calling syntax
    self.sudo("groupadd", self.config.shared_group)
    self.sudo("usermod", "-aG", "group", "user")
    # ... other commands
except sh.ErrorReturnCode as e:
    # Catch any command that fails
    logging.error(f"\n[FATAL] A command failed, halting execution.")
    logging.error(f"--> Command: '{e.full_cmd}'")
    logging.error(f"--> Stderr: {e.stderr.decode().strip()}")
    sys.exit(1)
```

This corrected pattern lets the `try...except` block handle any failure, which is the standard and recommended way to manage errors in Python.

-----

### **Future Prevention: Best Practices ✅**

To avoid this and similar issues when using the `sh` library, follow these guidelines:

1.  **Prioritize Standard `try...except` Blocks:** Always wrap your command calls in a `try...except sh.ErrorReturnCode` block. This is the most reliable and Pythonic way to handle command failures and is immune to bugs related to special underscore arguments.

2.  **Use Explicit Calling Syntax:** Prefer the `command("subcommand", "arg1")` syntax over the chained `command.subcommand("arg1")` syntax. It is less ambiguous and has proven to be more reliable.

3.  **Be Cautious with `.bake()`:** Only use `.bake()` to pre-configure parts of a command string (like `sh.sudo.bake("-E")`), not to set behavioral underscore arguments like `_ok_code` or `_raise_on_err`. Apply those arguments at the time of execution.

4.  **Always Clean the Python Cache:** After fixing code, a common source of continued failure is running stale, cached bytecode. Python stores this in `__pycache__` directories. Always run a cleanup command to ensure your changes are being executed. In your project, this is:

    ```bash
    make clean
    ```