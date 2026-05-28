#ifdef GL_ES
    precision mediump float;
#endif

uniform vec2 u_resolution;
uniform float u_time;
uniform float u_alpha_signal; 
uniform vec3 u_color;
uniform vec3 u_backgroundColor;

const float N = 20.0;

float mapRange(float value, float oldMin, float oldMax, float newMin, float newMax) {
    return newMin + (value - oldMin) / (oldMax - oldMin) * (newMax - newMin);
}

//This fragment shader draws concentric quantized rings whose radii are perturbed by a cosine function (giving petal-like bumps). The u_alpha_signal input is used to control zoom and how strong/finely the petals appear. Time (u_time) animates rotation and small radial wiggles.
void main() {
    // Calculate normalized pixel coordinates (from -1 to 1)
    vec2 u = (2.0 * gl_FragCoord.xy - u_resolution.xy) / u_resolution.y;
    float blendMode = smoothstep(10.0, 11.0, u_alpha_signal);
    float scale = mapRange(u_alpha_signal, 8.0, 13.0, .5, 3.0);
    // Apply the scaling to p to scale the drawing
    u *= scale;
    //Lower dynamic_N → larger perturbation amplitude → more pronounced petals.
    float dynamicA = mapRange(u_alpha_signal, 8.0, 13.0, N, 250.0);
    float dynamicB = mapRange(u_alpha_signal, 8.0, 13.0, N, 80.0);
    float dynamic_N = mix(dynamicA, dynamicB, blendMode);

    // Initialize time, radius, and angle
    float t = u_time * 5.0;
    //r and a are the polar coords
    float r = length(u);      // Radius
    float a = atan(u.y, u.x); // Angle in polar coordinates
    float period = 80.0;
    float raw = u_time * 4.0;
    float w = mod(raw, period);        // [0, period)

    // crossfade length (in same units as 'w'). Increase for a slower, smoother wrap.
    float eps = 6.0;                    // <- increase from 1.0 to something like 4..12 depending on taste

    // fade goes from 0 -> 1 as w approaches period
    float fade = smoothstep(period - eps, period, w);

    // compute the "other" wrapped time: one copy that continues forward (w), the other offset by -period
    float wA = w;            // normal
    float wB = w - period;   // wrapped copy

    // optional extra smoothing curve (smoothstep already cubic; this is an ease-in-out tweak)
    // fade = fade*fade*(3.0 - 2.0*fade); // uncomment if you want an even smoother ease

    // Build two modulation values and cross-fade them BEFORE quantization
    // base radius (unchanged)
    float r0 = r;

    // ttA and ttB drive the cosine perturbation that caused the jump
    float ttA = r0 + wA;
    float ttB = r0 + wB;

    // compute the small radial modulation for both states
    float modA = 1.0 - 0.1 * (0.5 + 0.5 * cos(r0 * ttA));
    float modB = 1.0 - 0.1 * (0.5 + 0.5 * cos(r0 * ttB));

    // blend the modulation smoothly
    float modMixed = mix(modA, modB, fade);
    float finalMod = mix(modMixed, 1.0, blendMode);
    // apply the mixed modulation to radius
    r *= finalMod;

    // Calculate index based on radius and adjust angle and radius
    //i is the integer ring index. Multiply radius by N (20) then floor → rings of thickness 1/N. i increments each time r crosses another 1/N threshold.
    //Because r later gets quantized by floor(N*r)/N, the band width is exactly 1/N.
    float i = floor(r * N);
    a *= floor(pow(128.0, i / N));
    //a += 10.0 * t adds global time rotation (note t = u_time*5.0, so this is actually 50.0 * u_time effect), and + 123.34 * i adds a per-ring phase offset so each ring’s cosine is rotated differently. Together these two give rotation and staggered petal orientation across rings.
    //float tot = 5.0;                     // duration of each mode (seconds)
    //float togglePeriod = tot * 2.0;      // full cycle: sin-mode + linear-mode
    // create a phase based on t (u_time*5.0) so it grows in sync
    //float phase = mod(t, togglePeriod);   // t = u_time * 5.0 from your code
    // two angle variants
    //float angleSin    = 20.0 * sin(t) + 123.34 * i - 100.0 * r;
    //float angleLinear = 10.0 * t      + 123.34 * i - 1.0 * (r - 0.1 * i / N);
    // choose which variant based on phase
    //float chosenAngle = (phase < tot) ? angleLinear : angleSin;
    // apply to the angle
    //a += chosenAngle;
    float a1 = a + 10.0 * t      + 123.34 * i - 1.0 * (r - 0.1 * i / N);
    float a2 = a + 10.0 * t      + 123.34 * i;
    float finalA = mix(a1, a2, blendMode);
    //This is the petal bump: cos(a) ranges [-1,1], so (0.5+0.5*cos(a)) ranges [0,1]. Dividing by dynamic_N makes the bumps small; smaller dynamic_N ⇒ larger bumps.
    r += (0.5 + 0.5 * cos(finalA)) / dynamic_N;
    //Quantizes the radius so rings are flat bands. Each band has thickness 1/N. This is what creates the crisp concentric steps.
    r = floor(N * r) / N;

    vec4 bg = vec4(u_backgroundColor, 1.0);
    vec4 ink = vec4(clamp(u_color, 0.0, 1.0), 1.0);
    // Combine background and ink color with smooth transition
    float blendFactor = smoothstep(0.001, 1.0, 1.0 - r);
    gl_FragColor = mix(bg, ink, blendFactor);
}
