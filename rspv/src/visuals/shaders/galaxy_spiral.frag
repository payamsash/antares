#ifdef GL_ES
    precision highp float;
#endif

uniform vec2 u_resolution;
uniform float u_time;
uniform vec3 u_color;
uniform vec3 u_backgroundColor;
uniform float u_alpha_signal;

#define rot(a) mat2(cos(a), -sin(a), sin(a), cos(a))
#define PI 3.14159265

// --- Hash / noise helpers ---
float hash(vec2 p) {
    p = mod(p, 289.0);
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
}
float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    float a = hash(i);
    float b = hash(i + vec2(1.0, 0.0));
    float c = hash(i + vec2(0.0, 1.0));
    float d = hash(i + vec2(1.0, 1.0));
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}
vec4 tex(vec2 U) {
    float T = noise(U * 250.0);
    float n = 1.0 - abs(2.0 * T - 1.0);
    return vec4(n, n, n, 1.0);
}
vec4 fractalTex(vec2 U) {
    U /= 10.0;
    return tex(U) * tex(2.0 * U) * tex(4.0 * U) * tex(8.0 * U);
}
float mapRange(float value, float oldMin, float oldMax, float newMin, float newMax) {
    return newMin + (value - oldMin) / (oldMax - oldMin) * (newMax - newMin);
}


// --- deterministic particle field fixed in screen-space ---
float particleFieldScreen(vec2 uv, float t, int count, float sizeScale, float lifeSpan) {
    float sum = 0.0;
    vec2 aspect = vec2(u_resolution.x / u_resolution.y, 1.0);
    const float MAX_PART = 30.0;
    for (float i = 0.0; i < MAX_PART; i += 1.0) {
        if (i >= float(count)) break;
        float si = i + 1.0;
        float r1 = hash(vec2(si, 12.34));
        float r2 = hash(vec2(si, 56.78));
        float r3 = hash(vec2(si, 90.12));
        float r4 = hash(vec2(si, 34.56));
        vec2 pcenter = vec2(r1, r2);
        float phase = fract(r3 + t * 0.25);
        float alive = step(phase, lifeSpan);
        float fadeIn = smoothstep(0.0, 0.3 * lifeSpan, phase);
        float fadeOut = 1.0 - smoothstep(lifeSpan - 0.5 * lifeSpan, lifeSpan, phase);
        float lifeFade = fadeIn * fadeOut * alive;
        vec2 jitter = vec2(
            sin(2.0 * PI * (t * (0.08 + r4 * 0.25) + r1 * 23.7)),
            cos(2.0 * PI* (t * (0.10 + r4 * 0.23) + r2 * 17.3))
        ) * 0.007 * (1.0 - phase);
        pcenter += jitter;
        float psize = sizeScale * (0.6 + 0.8 * r4);
        vec2 d = (uv - pcenter) * aspect;
        float dist = length(d);
        float mask = exp(- (dist * dist) / (psize * psize) * 6.0);
        sum += mask * lifeFade;
    }
    return sum;
}

void main() {
    vec2 frag = gl_FragCoord.xy;
    vec2 uv_screen = frag / u_resolution;
    vec2 u = (2.0 * frag - u_resolution) / u_resolution.y;

    float scaleMod = 1.0 + 0.2 * sin(u_time * 0.3);
    float scale = mapRange(u_alpha_signal, 8.0, 13.0, 3.5, 20.0) * scaleMod * 0.35;
    float radx = mapRange(u_alpha_signal, 8.0, 13.0, 0.8, 0.3);
    float thickness = mapRange(u_alpha_signal, 8.0, 13.0, 0.3, 0.8);
    float rot_param = 1.6 + 0.025 * u_time;

    vec2 u_scaled = u * scale;

    vec4 O = vec4(0.0);
    vec2 r = vec2(radx, 0.3);
    float angleStep = -PI / rot_param;
    for (float l = 1.6; l < 3.5; l += 0.1) {
        vec2 V = 1.0 / r * (rot(angleStep + angleStep * l) * u_scaled);
        float d = dot(V, V);
        float va = u_time * (1.5 / l);
        vec4 C = fractalTex(rot(va + l) * 0.6 * V / l);
        float ringMask = smoothstep(thickness, 0.0, abs(sqrt(d) - l));
        O += ringMask * C / l;
    }
    
    vec3 spiralColor = mix(u_backgroundColor, u_color, O.r);

    /*int pCount = 100;
    float sizeScale = 0.005;
    float lifeSpan = 1.0;
    float expansionFactor = max(0.0, cos(u_time * 0.3));
    float particlesRaw = particleFieldScreen(uv_screen, u_time, pCount, sizeScale, lifeSpan);
    float particles = particlesRaw * (0.25 + 0.5 * expansionFactor);
    vec3 particleColor = u_color;

    vec3 particleLayer = particleColor * particles; 

    vec3 finalCol = mix(spiralColor, particleColor, particles * 1.0);
    finalCol *= exp(-O.r / 8.0);
        gl_FragColor = vec4(clamp(finalCol, 0.0, 1.0), 1.0);*/
    spiralColor *= exp(-O.r / 8.0);
    gl_FragColor = vec4(clamp(spiralColor, 0.0, 1.0), 1.0);

}
