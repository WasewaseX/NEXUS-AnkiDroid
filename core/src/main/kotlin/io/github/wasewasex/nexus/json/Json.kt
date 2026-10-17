package io.github.wasewasex.nexus.json

import com.google.gson.Gson
import com.google.gson.GsonBuilder

/** Single Gson instance for the whole app (pretty-printed, stable output for round-trips). */
object Json {
    val gson: Gson = GsonBuilder().setPrettyPrinting().disableHtmlEscaping().create()

    fun toJson(x: Any): String = gson.toJson(x)

    inline fun <reified T> fromJson(s: String): T = gson.fromJson(s, T::class.java)
}
