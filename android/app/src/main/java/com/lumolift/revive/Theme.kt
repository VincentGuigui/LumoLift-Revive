package com.lumolift.revive

import android.os.Build
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.foundation.isSystemInDarkTheme

private val Light = lightColorScheme(
    primary = Color(0xFF006B5F),
    secondary = Color(0xFF4A635F),
    tertiary = Color(0xFF456179),
    surface = Color(0xFFF7FAF8),
)
private val Dark = darkColorScheme(primary = Color(0xFF53DBC7), secondary = Color(0xFFB1CCC6))

@Composable
fun LumoTheme(content: @Composable () -> Unit) {
    val dark = isSystemInDarkTheme()
    val context = LocalContext.current
    val colors = if (Build.VERSION.SDK_INT >= 31) {
        if (dark) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
    } else if (dark) Dark else Light
    MaterialTheme(colorScheme = colors, content = content)
}
