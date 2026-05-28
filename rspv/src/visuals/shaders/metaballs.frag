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
uniform int u_total;

void main() {
    // normalized uv [0..1], origin bottom-left
    vec2 uv = gl_FragCoord.xy / u_resolution;
    uv.y = 1.0 - uv.y;

    vec3 bg = u_backgroundColor;

    vec3 accum = vec3(0.0);
    float accW = 0.0;

    for (int i = 0; i < MAX_TOTAL; i++) {
        if (i >= u_total) break;
        vec2 p = vec2(posX[i], posY[i]);
        // distance in normalized coords
        float d = distance(uv, p);
        // SIZE is expected normalized (fraction of min(width,height))
        float s = max(SIZE[i], 0.000001);
        float dist = pow(d * u_intensity, u_contour) / s;
        accum += vec3(R[i], G[i], B[i]) / dist;
        accW += 1.0 / dist;
    }

    vec3 outColor = bg;
    float threshold = pow(20.0, u_contour);
    if (accW > 0.0) {
        vec3 metaballColor = accum / max(accW, 1e-6);
        float t = smoothstep(threshold * 0.97, threshold, accW);
        outColor = mix(bg, metaballColor, t);
    }

    gl_FragColor = vec4(outColor, 1.0);
}
