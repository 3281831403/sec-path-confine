"""Path-confinement contract for the upload-preview service.

The eight public functions below implement a strict containment contract:
all filesystem-facing functions use real paths, and comparisons have zero
tolerance (no prefix, fuzzy, or case-sensitive shortcuts).
"""

from __future__ import annotations

import ntpath
import os
import posixpath
import unicodedata


def normalize(path: str) -> str:
    """Normalize *path* for confinement checks.

    Contract:
    - Apply NFKC, convert the fullwidth solidus, the fullwidth reverse
      solidus, and the ASCII backslash to "/", then casefold.  This is the
      fixed case policy for the Windows upload service.
    - Collapse empty and "." segments and resolve ".." segments one at a
      time.  A leading run of ".." is preserved for relative paths; repeated
      dot-dot segments must never survive in the middle of the result.
    - Preserve relativeness: a relative input never gains a leading "/".
      An empty input normalizes to ".".
    - This function is pure and does not touch the filesystem, so it cannot
      perform real-path resolution.  Root confinement is enforced by
      :func:`safe_join`; the root directory is not implicit here.
    - Tolerance is 0: the returned spelling is the exact spelling used by
      every later comparison.
    """
    # Defect 07: NFKC folds fullwidth letters and slash variants; the explicit
    # replacements also catch any form NFKC leaves behind, then casefold fixes
    # the case policy.  Nothing here is filesystem-dependent.
    text = unicodedata.normalize("NFKC", path)
    text = text.replace("＼", "/").replace("\\", "/").replace("／", "/")
    text = text.casefold()

    is_unc = text.startswith("//")
    is_absolute = is_unc or text.startswith("/")

    # Defect 01: collapse empty/"." segments and resolve ".." one segment at a
    # time.  A ".." only pops a real directory segment; once the stack holds a
    # leading run of ".." (or is empty on a relative path), further ".."
    # segments stay at the front.  Dot-dot can never survive in the middle.
    stack: list[str] = []
    for segment in text.split("/"):
        if segment == "" or segment == ".":
            continue
        if segment == "..":
            if stack and stack[-1] != "..":
                stack.pop()
            else:
                stack.append("..")
        else:
            stack.append(segment)

    result = "/".join(stack)
    if is_unc:
        return "//" + result
    if is_absolute:
        return "/" + result
    return result if result else "."


def is_absolute_escape(path: str) -> bool:
    """Return True when *path* is absolute or drive-qualified.

    Contract:
    - Normalize first, then detect a POSIX absolute path, a UNC path, or a
      Windows drive form.  Both ``C:\\uploads\\x`` and ``C:relative`` are
      drive-qualified escapes and must return True; a drive changes the root.
    - Ordinary relative paths, including paths beginning with "..", are not
      absolute escapes.
    - No filesystem access and no real-path resolution occurs here.  The
      root directory constraint is enforced by the caller, chiefly
      :func:`safe_join`.
    - Tolerance is 0: only the exact normalized forms decide the answer.
    """
    # Defect 06: check every absolute spelling, including the drive-relative
    # form "D:file" that has no separator after the colon.
    normalized = normalize(path)
    if normalized.startswith("/"):
        return True
    if (
        len(normalized) >= 2
        and normalized[1] == ":"
        and normalized[0].isalpha()
    ):
        return True
    return False


def _has_leading_dotdot(normalized: str) -> bool:
    """True when a normalized relative path escapes its base directory."""
    return normalized == ".." or normalized.startswith("../")


def resolve(root: str, path: str) -> str:
    """Join *path* beneath *root* and return its real path.

    Contract:
    - *root* must be an absolute directory path; otherwise raise ValueError.
      *path* must be relative, and an absolute or drive-qualified path is
      rejected with ValueError before joining.
    - Normalize *path*, join it to the real path of *root*, then apply
      ``os.path.realpath`` so symbolic links, junctions, and dot-dot
      segments are resolved against the actual filesystem.
    - The returned value is a real path.  This function does not itself
      enforce containment: a link may legitimately resolve outside, and
      :func:`within` / :func:`safe_join` decide whether that is acceptable.
    - Tolerance is 0: the real-path string is compared exactly after the
      shared normalization.
    """
    if not os.path.isabs(root) or not os.path.isdir(root):
        raise ValueError("root must be an absolute, existing directory")
    if is_absolute_escape(path):
        raise ValueError("path must be relative, not absolute or drive-qualified")

    normalized = normalize(path)
    root_real = os.path.realpath(root)
    joined = root_real if normalized == "." else os.path.join(root_real, normalized)
    # Defect 04: realpath resolves symlinks/junctions against the actual
    # filesystem, so a link-based escape is visible in the returned string.
    return os.path.realpath(joined)


def within(root: str, resolved: str) -> bool:
    """Return True when *resolved* is *root* or a real descendant.

    Contract:
    - Both arguments are absolute, already-resolved paths.  This is a pure
      lexical comparison on normalized strings; it does not touch the
      filesystem, and root confinement is the caller's responsibility.
    - Compare at directory boundaries.  The root itself is within the root;
      a child such as root/upload/report.txt is within; a same-prefix sibling
      such as root/upload_backup/secret.txt is not.
    - Apply the case policy from :func:`normalize`, and require an explicit
      separator after the root for descendants.  Never use a bare string
      prefix.
    - Tolerance is 0: segment spelling must match exactly after
      normalization, with no allowance for extra or missing separators.
    """
    normalized_root = normalize(root)
    normalized_resolved = normalize(resolved)

    # Defect 03: the root itself is inside the root.
    if normalized_resolved == normalized_root:
        return True
    # Defect 02: require a directory separator after the root instead of a
    # bare string prefix, so same-prefix siblings cannot pass.
    return normalized_resolved.startswith(normalized_root + "/")


def safe_join(root: str, path: str) -> str:
    """Return a real path guaranteed to stay inside *root*.

    Contract:
    - *root* must be an absolute directory path; *path* must be relative.
      Absolute, drive-qualified, and UNC inputs raise ValueError.  The empty
      path maps to the root itself.
    - Normalize the relative path and reject any leading ".." escape before
      joining.  Then use :func:`resolve` to obtain the real path and
      :func:`within` to enforce the directory boundary with zero tolerance.
    - The link target must also stay inside: call :func:`check_symlink` so a
      link or junction is judged by its resolved target, not by its name.
    - On any escape raise ValueError.  Never return an empty string and never
      fall back to the process working directory.
    - Tolerance is 0: the returned real path must be exactly the root or an
      exact descendant of it.
    """
    if not os.path.isabs(root) or not os.path.isdir(root):
        raise ValueError("root must be an absolute, existing directory")
    if is_absolute_escape(path):
        raise ValueError("absolute, drive-qualified, or UNC paths are not allowed")

    normalized = normalize(path)
    if _has_leading_dotdot(normalized):
        # Defect 10: raise instead of returning an empty string that callers
        # might resolve against their working directory.
        raise ValueError("relative path escapes the root")

    resolved = resolve(root, path)
    if not within(root, resolved):
        raise ValueError("resolved real path escapes the root")
    if not check_symlink(root, path):
        raise ValueError("symlink target escapes the root")
    return resolved


def check_symlink(root: str, path: str) -> bool:
    """Return True when *path* resolves inside *root*, including link targets.

    Contract:
    - *root* must be absolute; *path* is interpreted relative to *root*.
      Resolve the real path rather than inspecting only a basename or a link
      name.  A link called report.txt that points outside is unsafe even when
      its name matches an internal file name.
    - A regular path inside the root returns True.  An absolute,
      drive-qualified, or ".."-escaping path returns False rather than
      raising.  A link whose resolved target is outside returns False.
    - Missing path tails are still checked lexically after real-path
      resolution; the root directory constraint is never relaxed.
    - Tolerance is 0: the link target must be the root or an exact
      descendant at a directory boundary.
    """
    if not os.path.isabs(root):
        return False
    if is_absolute_escape(path):
        return False
    if _has_leading_dotdot(normalize(path)):
        return False

    try:
        # Defect 05: judge the resolved target, not the link's basename.
        resolved = resolve(root, path)
    except ValueError:
        return False
    return within(root, resolved)


def validate_policy(policy: dict) -> list[str]:
    """Return the security problems found in *policy*.

    Contract:
    - *policy* is a mapping with ``root``, ``resolve_symlinks``, and
      ``allow_absolute``.  A restricted root is a non-empty absolute path;
      links must be resolved (``resolve_symlinks is True``); absolute paths
      must be disallowed (``allow_absolute is False``).
    - Return issues in this fixed order: unresolved links first, then an
      unrestricted root, then permission for absolute paths.  The exact
      strings are ``"symlinks are not resolved"``, ``"root is not
      restricted"``, and ``"absolute paths are allowed"``.
    - A compliant policy returns an empty list.  Missing security settings
      fail closed (missing links resolution or absolute-path setting is an
      issue); the root must be a real, absolute containment boundary.
    - Tolerance is 0: boolean settings are checked strictly, and the root is
      not accepted with a relative or empty spelling.
    """
    issues: list[str] = []

    # Defect 08: strict boolean checks; missing keys fail closed.
    if policy.get("resolve_symlinks") is not True:
        issues.append("symlinks are not resolved")

    root = policy.get("root")
    if not isinstance(root, str) or not root or not os.path.isabs(root):
        issues.append("root is not restricted")

    if policy.get("allow_absolute") is not False:
        issues.append("absolute paths are allowed")

    return issues


def join_batch(root: str, paths: list[str]) -> dict[str, str]:
    """Safely join each relative path under *root*.

    Contract:
    - Return a dictionary keyed by each original input string, with the
      corresponding real path from :func:`safe_join` as the value.
    - Every call uses the *root* argument of that call.  No module-level or
      closure cache may reuse a previous root; two batches with different
      roots are independent.
    - Each path is processed independently through :func:`safe_join`, which
      enforces the root constraint.  If any path escapes, raise ValueError;
      never return a partial result or an empty-string path.
    - An empty batch returns an empty dictionary.  Tolerance is 0: keys are
      the original spellings and values are exact real paths.
    """
    # Defect 09: no shared/module-level root state; each entry goes through
    # safe_join with this call's root argument, and an escape propagates.
    return {item: safe_join(root, item) for item in paths}
