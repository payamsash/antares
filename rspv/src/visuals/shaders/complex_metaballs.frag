#ifdef GL_ES
precision mediump float;
#endif

#define MAX_TOTAL 16

uniform vec2 u_resolution;
uniform vec3 u_backgroundColor;
uniform float u_intensity;
uniform float u_contour;

uniform float posX[MAX_TOTAL];
uniform float posY[MAX_TOTAL];
uniform float R[MAX_TOTAL];
uniform float G[MAX_TOTAL];
uniform float B[MAX_TOTAL];
uniform float SIZE[MAX_TOTAL];
uniform float SHAPE_TYPE[MAX_TOTAL];
uniform float WEIGHT[MAX_TOTAL];
uniform int   u_total;

// Thickness in "pixel-like" units (scaled by min resolution dimension)
const float THICKNESS_PX_DYNAMIC = 0.2; // non-persistent shapes
const float THICKNESS_PX_PERSIST = 0.1; // persistent capsule outlines (thinner)

// Filled circle (st == 0)
float metric_circle(vec2 uv, vec2 center) {
    return distance(uv, center);
}

// Circular ring (st == 1)
float metric_ring(vec2 uv, vec2 center, float radius, float thickness_uv) {
    vec2 p = uv - center;
    float base = length(p);
    float sdf = abs(base - radius) - thickness_uv;
    return max(sdf, 0.0);
}

// Box ring (st == 2)
float metric_box_ring(vec2 uv, vec2 center, float radius, float thickness_uv) {
    vec2 p = uv - center;
    vec2 d = abs(p);
    float base = max(d.x, d.y);
    float sdf0 = base - radius;
    float sdf = abs(sdf0) - thickness_uv;
    return max(sdf, 0.0);
}

// Diamond ring (st == 3)
float metric_diamond_ring(vec2 uv, vec2 center, float radius, float thickness_uv) {
    vec2 p = uv - center;
    vec2 d = abs(p);
    float l1 = d.x + d.y;
    float sdf0 = l1 - radius;
    float sdf = sdf0 * 0.70710678;
    sdf = abs(sdf) - thickness_uv;
    return max(sdf, 0.0);
}

// Vertical capsule ring (st == 4) — ellipse outline, taller than wide
float metric_capsule_vertical_ring(vec2 uv, vec2 center, float radius, float thickness_uv) {
    vec2 p = uv - center;
    float ax = radius * 0.5;
    float ay = radius * 1.4;

    vec2 q = vec2(p.x / ax, p.y / ay);
    float sdf0 = length(q) - 1.0;
    float k = min(ax, ay);
    float sdf = sdf0 * k;
    sdf = abs(sdf) - thickness_uv;
    return max(sdf, 0.0);
}

// Horizontal capsule ring (st == 5) — ellipse outline, wider than tall
float metric_capsule_horizontal_ring(vec2 uv, vec2 center, float radius, float thickness_uv) {
    vec2 p = uv - center;
    float ax = radius * 1.4;
    float ay = radius * 0.5;

    vec2 q = vec2(p.x / ax, p.y / ay);
    float sdf0 = length(q) - 1.0;
    float k = min(ax, ay);
    float sdf = sdf0 * k;
    sdf = abs(sdf) - thickness_uv;
    return max(sdf, 0.0);
}

float shape_metric(int st, vec2 uv, vec2 center, float s, float thickness_uv) {
    float d;
    if (st == 0) {
        d = metric_circle(uv, center);
    } else if (st == 1) {
        d = metric_ring(uv, center, s, thickness_uv);
    } else if (st == 2) {
        d = metric_box_ring(uv, center, s, thickness_uv);
    } else if (st == 3) {
        d = metric_diamond_ring(uv, center, s, thickness_uv);
    } else if (st == 4) {
        d = metric_capsule_vertical_ring(uv, center, s, thickness_uv);
    } else {
        d = metric_capsule_horizontal_ring(uv, center, s, thickness_uv);
    }
    return max(d, 1e-4);
}

void main() {
    vec2 uv = gl_FragCoord.xy / u_resolution;
    uv.y = 1.0 - uv.y;

    vec3 bg = u_backgroundColor;
    vec3 accum = vec3(0.0);
    float accW = 0.0;

    float minRes = min(u_resolution.x, u_resolution.y);

    for (int i = 0; i < MAX_TOTAL; i++) {
        if (i >= u_total) break;

        vec2  p  = vec2(posX[i], posY[i]);
        float s  = max(SIZE[i], 0.000001);

        int st = int(floor(SHAPE_TYPE[i] + 0.5));

        // Capsule outlines (4, 5) are persistent anchors — use thinner lines
        float thicknessPx = (st == 4 || st == 5) ? THICKNESS_PX_PERSIST : THICKNESS_PX_DYNAMIC;
        float thickness_uv = thicknessPx / minRes;

        float d    = shape_metric(st, uv, p, s, thickness_uv);
        float dist = pow(d * u_intensity, u_contour) / s;

        float w = WEIGHT[i];

        vec3 col = vec3(R[i], G[i], B[i]);
        accum += (col * w) / dist;
        accW  +=        w  / dist;
    }

    vec3  outColor  = bg;
    float threshold = pow(20.0, u_contour);

    if (accW > 0.0) {
        vec3  metaballColor = accum / max(accW, 1e-6);
        float t = smoothstep(threshold * 0.97, threshold, accW);
        outColor = mix(bg, metaballColor, t);
    }

    gl_FragColor = vec4(outColor, 1.0);
}
