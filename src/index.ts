import { Engine } from "@babylonjs/core/Engines/engine";
import { WebGPUEngine } from "@babylonjs/core/Engines/webgpuEngine";
import { Scene } from "@babylonjs/core";
import "@babylonjs/core/Engines/WebGPU/Extensions/engine.uniformBuffer";
import { ArcRotateCamera } from "@babylonjs/core/Cameras";
import { Vector3 } from "@babylonjs/core/Maths";
import { SceneLoader } from "@babylonjs/core/Loading";
import { HemisphericLight } from "@babylonjs/core/Lights";
import "@babylonjs/core/Loading/loadingScreen";
import "@babylonjs/loaders/glTF";
import "@babylonjs/core/Materials/standardMaterial";
import "@babylonjs/core/Materials/Textures/Loaders/envTextureLoader";


import rigMesh from "../assets/glb/rig.glb";

export const babylonInit = async (): Promise<void> => {
    const canvas = document.getElementById("renderCanvas") as HTMLCanvasElement;
    let engine: Engine;
    const engineType =
        location.search.split("engine=")[1]?.split("&")[0] || "webgl";
    if (engineType === "webgpu") {
        const webGPUSupported = await WebGPUEngine.IsSupportedAsync;
        if (webGPUSupported) {
            const webgpu = engine = new WebGPUEngine(canvas, {
                adaptToDeviceRatio: true,
                antialiasing: true,
            });
            await webgpu.initAsync();
            engine = webgpu;
        } else {
            engine = new Engine(canvas, true);
        }
    } else {
        engine = new Engine(canvas, true);
    }

    const scene = new Scene(engine);
    void Promise.all([
        import("@babylonjs/core/Debug/debugLayer"),
        import("@babylonjs/inspector"),
    ]).then((_values) => {
        console.log(_values);
        scene.debugLayer.show({
            handleResize: true,
            overlay: true,
            globalRoot: document.getElementById("#root") || undefined,
        });
    });

    const camera = new ArcRotateCamera(
        "cam",
        0,
        Math.PI / 3,
        20,
        new Vector3(0, 0, 0),
        scene
    );
    camera.setTarget(Vector3.Zero());
    camera.attachControl(canvas, true);

    await buildScene(scene)

    engine.runRenderLoop(function () {
        scene.render();
    });
    window.addEventListener("resize", function () {
        engine.resize();
    });
};

async function buildScene(scene: Scene) {
    const light = new HemisphericLight(
        "light",
        new Vector3(0, 1, 0),
        scene
    );
    light.intensity = 0.7;

    const importResult = await SceneLoader.ImportMeshAsync(
        "",
        "",
        rigMesh,
        scene,
        undefined,
        ".glb"
    );

    console.log(importResult);

}

babylonInit().then(() => {
    // scene started rendering, everything is initialized
});
