"""SQL fragments the wishlist shares with other packages. It imports nothing, so posts and the
wishlist repository can both use it without an import cycle."""

# Whether the caller's own list holds a title, for other queries. `{title}` is a column reference
# (or a bind parameter). It reflects nobody else's list (plan P5); the inner alias keeps it from
# capturing an outer column.
IN_WISHLIST_SQL = (
    "EXISTS (SELECT 1 FROM app.wishlist_items wl_own"
    " WHERE wl_own.owner_id = auth.uid() AND wl_own.title_id = {title})"
)
