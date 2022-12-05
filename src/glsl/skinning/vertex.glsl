precision highp float;

// Attributes
attribute vec3 position;
attribute vec3 normal;
attribute vec3 color;

// Uniforms
uniform mat4 world;
uniform mat4 worldViewProjection;

varying vec3 vColor;

void main(void) {
    vec4 outPosition = worldViewProjection * vec4(position, 1.0);
    gl_Position = outPosition;
    vColor = color;
}
    