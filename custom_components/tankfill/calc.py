"""Volume calculation for a horizontal cylindrical tank."""

import math


def segment_volume(fill_depth: float, diameter: float, length: float) -> float:
    """Calculate volume of a circular segment in a horizontal cylinder.

    Uses the circular segment formula for liquid depth measured from the bottom.

    Args:
        fill_depth: Depth of liquid from the bottom in cm.
        diameter: Tank diameter in cm.
        length: Tank length in cm.

    Returns:
        Volume in litres.
    """
    if fill_depth <= 0:
        return 0.0
    if fill_depth >= diameter:
        radius = diameter / 2
        return math.pi * radius**2 * length / 1000

    radius = diameter / 2
    m = radius - fill_depth
    area_of_sector = math.acos(m / radius) * radius**2
    area_of_triangle = m * math.sqrt(2 * radius * fill_depth - fill_depth**2)
    return (area_of_sector - area_of_triangle) * length / 1000


def max_volume(diameter: float, length: float) -> float:
    """Calculate maximum volume of a horizontal cylindrical tank in litres."""
    radius = diameter / 2
    return math.pi * radius**2 * length / 1000


def calculate_volume(
    sensor_distance: float, diameter: float, length: float
) -> float:
    """Calculate volume of liquid given the sensor distance from the top.

    The sensor reports distance from the top of the tank to the liquid
    surface. When the tank is less than or equal to half full, we convert
    to liquid depth and use the segment formula directly. When more than
    half full, we calculate the full volume minus the empty space (the
    sensor distance is the height of the empty space).

    Args:
        sensor_distance: Distance from top of tank to liquid surface in cm.
        diameter: Tank diameter in cm.
        length: Tank length in cm.

    Returns:
        Volume in litres.
    """
    if sensor_distance >= diameter:
        return 0.0
    if sensor_distance <= 0:
        return max_volume(diameter, length)

    liquid_depth = diameter - sensor_distance

    if liquid_depth <= diameter / 2:
        # Less than or equal to half full - use segment formula with liquid depth
        return segment_volume(liquid_depth, diameter, length)

    # More than half full - total volume minus the empty space above the liquid.
    # sensor_distance is the height of the empty space from the top.
    return max_volume(diameter, length) - segment_volume(
        sensor_distance, diameter, length
    )
