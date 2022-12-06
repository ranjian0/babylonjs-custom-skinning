precision highp float;

varying vec3 vColor;
varying vec3 vNormal;

void main(void) {
    // vec3 light = vec3(0.0, -1.0, 7.0);
    // float lum = dot(normalize(light), normalize(vNormal));

    gl_FragColor = vec4(vColor, 1.0);
}