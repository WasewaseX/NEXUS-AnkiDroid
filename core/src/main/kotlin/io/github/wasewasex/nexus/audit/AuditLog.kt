package io.github.wasewasex.nexus.audit

/**
 * Append-only audit trail. Every NEXUS intervention decision (selected or skipped), every
 * budget state change and every delayed assessment is recorded here with a human-readable
 * rationale. Nothing ever deletes entries; exports include the full log.
 */
class AuditEntry(
    var millis: Long = 0,
    var kind: String = "",
    var payload: LinkedHashMap<String, String> = LinkedHashMap(),
)

class AuditLog {
    var entries: ArrayList<AuditEntry> = ArrayList()

    fun add(kind: String, vararg pairs: Pair<String, String>): AuditEntry {
        val e = AuditEntry(System.currentTimeMillis(), kind, LinkedHashMap())
        for (p in pairs) e.payload[p.first] = p.second
        entries.add(e)
        return e
    }

    fun last(n: Int): List<AuditEntry> = entries.takeLast(n)
}
