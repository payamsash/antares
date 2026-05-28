#ifdef GL_ES
precision mediump float;
#endif

uniform vec2 u_resolution;
uniform float u_time;
uniform float u_alpha_signal; 
uniform vec3 u_inkColor;
uniform vec3 u_backgroundColor;

// -------------------- Constants --------------------
const float MASK_TIME_SCALE     = 0.1;
const float MASK_TIME_OFFSET    = 30.0;
const float TEXTURE_TIME_SCALE  = 0.04;
const float TEXTURE_TIME_OFFSET = 256.0;
const float SMOOTH_EDGE_WIDTH   = 0.03;

// -------------------- Noise Helpers --------------------
vec4 permute(vec4 x) {
    return mod(((x * 34.0) + 1.0) * x, 289.0);
}

vec4 taylorInvSqrt(vec4 r) {
    return 1.79284291400159 - 0.85373472095314 * r;
}

// Simplex noise (3D)
float snoise(vec3 v) { 
    const vec2 C = vec2(1.0 / 6.0, 1.0 / 3.0);
    const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);

    vec3 i = floor(v + dot(v, C.yyy));
    vec3 x0 = v - i + dot(i, C.xxx);

    vec3 g = step(x0.yzx, x0.xyz);
    vec3 l = 1.0 - g;
    vec3 i1 = min(g.xyz, l.zxy);
    vec3 i2 = max(g.xyz, l.zxy);

    vec3 x1 = x0 - i1 + C.xxx;
    vec3 x2 = x0 - i2 + 2.0 * C.xxx;
    vec3 x3 = x0 - 1.0 + 3.0 * C.xxx;

    i = mod(i, 289.0);
    vec4 p = permute(permute(permute(
                 i.z + vec4(0.0, i1.z, i2.z, 1.0)) +
                 i.y + vec4(0.0, i1.y, i2.y, 1.0)) +
                 i.x + vec4(0.0, i1.x, i2.x, 1.0));

    float n_ = 1.0 / 7.0;
    vec3 ns = n_ * D.wyz - D.xzx;

    vec4 j = p - 49.0 * floor(p * ns.z * ns.z);
    vec4 x_ = floor(j * ns.z);
    vec4 y_ = floor(j - 7.0 * x_);
    vec4 x = x_ * ns.x + ns.yyyy;
    vec4 y = y_ * ns.x + ns.yyyy;
    vec4 h = 1.0 - abs(x) - abs(y);

    vec4 b0 = vec4(x.xy, y.xy);
    vec4 b1 = vec4(x.zw, y.zw);

    vec4 s0 = floor(b0) * 2.0 + 1.0;
    vec4 s1 = floor(b1) * 2.0 + 1.0;
    vec4 sh = -step(h, vec4(0.0));

    vec4 a0 = b0.xzyw + s0.xzyw * sh.xxyy;
    vec4 a1 = b1.xzyw + s1.xzyw * sh.zzww;

    vec3 p0 = vec3(a0.xy, h.x);
    vec3 p1 = vec3(a0.zw, h.y);
    vec3 p2 = vec3(a1.xy, h.z);
    vec3 p3 = vec3(a1.zw, h.w);

    vec4 norm = taylorInvSqrt(
        vec4(dot(p0, p0), dot(p1, p1), dot(p2, p2), dot(p3, p3))
    );
    p0 *= norm.x; p1 *= norm.y; p2 *= norm.z; p3 *= norm.w;

    vec4 m = max(0.6 - vec4(
        dot(x0, x0), dot(x1, x1),
        dot(x2, x2), dot(x3, x3)), 0.0);
    m = m * m;

    return 42.0 * dot(m * m,
        vec4(dot(p0, x0), dot(p1, x1),
             dot(p2, x2), dot(p3, x3)));
}

// Fractal Brownian Motion
float fbm(vec3 p, int octaves) {
    float value = 0.0;
    float amplitude = 0.5;
    float frequency = 1.0;

    for (int i = 0; i < octaves; i++) {
        value += amplitude * snoise(p * frequency);
        frequency *= 2.0;
        amplitude *= 0.5;
    }
    return value;
}

float mapRange(float v, float inMin, float inMax, float outMin, float outMax) {
    return outMin + (v - inMin) / (inMax - inMin) * (outMax - outMin);
}

// -------------------- Ink Logic --------------------
// create a mask i1 by combining fbm noise and radial bias
// the smoothstep creates an irregular blot silhouette. 
// Increasing the second param (.03) makes the mask more blur. 
// Increasing the first param makes the mask more clear.
// adding length(uv) * alpha_scale biases the field positively as you move away from center, 
// so the mask tends to be contained near the center. 
// The bigger alpha_scale, the faster the radius term pushes v positive — meaning the ink blob will be smaller (it reaches the threshold sooner). 
// So higher alpha_scale → smaller, more concentrated blot.
// increase u_time to make the animation faster
float inkMask(vec2 uv, vec2 abs_uv, float alpha_scale, int octaves, float time) {
    float noiseField = fbm(vec3(abs_uv, time * MASK_TIME_SCALE + MASK_TIME_OFFSET), octaves);
    float radialBias = -0.15 + length(uv) * alpha_scale;
    float maskValue = noiseField + radialBias;
    return 1.0 - smoothstep(0.0, SMOOTH_EDGE_WIDTH, maskValue);
}

// Mixes background and ink color using that mask plus a second fbm that modulates interior ink strength
// this second fbm uses uv (not abs_uv) so the silhouette is symmetric but the interior texture is not necessarily mirrored
float inkTexture(vec2 uv, float time) {
    return fbm(vec3(uv * 0.75, time * TEXTURE_TIME_SCALE + TEXTURE_TIME_OFFSET), 5);
}

// -------------------- Main --------------------
void main() {
    vec2 uv = (2.0 * gl_FragCoord.xy - u_resolution.xy) / u_resolution.y;
    //horiz simmetry
    vec2 abs_uv = vec2(abs(uv.x), uv.y);
    // u_alpha_signal is normalised to [0, 1] by the Python signal pipeline.
    // 0 = poor performance (large, complex blot); 1 = good performance (small, smooth blot).
    float alpha_scale = mapRange(u_alpha_signal, 0.0, 1.0, 0.2, 2.0);

    // higher signal → fewer octaves → smoother edge
    float octave_f = mapRange(u_alpha_signal, 0.0, 1.0, 8.0, 5.0);
    int octaves = int(max(1.0, floor(octave_f + 0.5)));

    // Ink silhouette mask
    float mask = inkMask(uv, abs_uv, alpha_scale, octaves, u_time);

    // Interior ink texture
    float textureStrength = inkTexture(uv, u_time);

    // Mix factor
    float inkMix = mask * (0.6 + 0.5 * textureStrength);

    // t=1 at signal=0 (background visible); t=0 at signal=1 (ink floods screen)
    float t = 1.0 - u_alpha_signal;
    // ease the transition:
    float bgLerp = smoothstep(0.0, 1.0, t);

    // resulting background color to use for the final mix:
    vec3 bgColor = mix(u_inkColor, u_backgroundColor, bgLerp);
    // -----------------------

    vec3 color = mix(bgColor, u_inkColor, inkMix);

    gl_FragColor = vec4(color, 1.0);
}
