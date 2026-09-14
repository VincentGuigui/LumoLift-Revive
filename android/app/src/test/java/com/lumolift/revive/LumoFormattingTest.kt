package com.lumolift.revive

import org.junit.Assert.assertEquals
import org.junit.Test

class LumoFormattingTest {
    @Test
    fun batteryLabelTreatsPercentAsLiteralText() {
        assertEquals("50% · 3.85 V", formatBatteryLabel(50, 3.8457))
    }
}
