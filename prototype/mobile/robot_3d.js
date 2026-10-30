import * as THREE from "three";
import { GLTFLoader } from "./vendor/loaders/GLTFLoader.js?v=29";

const canvas = document.querySelector("#robotPreviewCanvas");
const fallback = document.querySelector("#robotPreviewFallback");
const homeMount = document.querySelector("#homeRobotMount");
const remoteMount = document.querySelector("#remoteRobotMount");

if (canvas) {
  const scene = new THREE.Scene();
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.08;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  const camera = new THREE.PerspectiveCamera(27, 1, .1, 100);
  camera.position.set(0, 1.08, 6.5);
  camera.lookAt(0, 1.02, 0);

  const keyLight = new THREE.DirectionalLight(0xffffff, 2.5);
  keyLight.position.set(3.8, 5.2, 4.6);
  keyLight.castShadow = true;
  keyLight.shadow.mapSize.set(1024, 1024);
  scene.add(keyLight);
  const fillLight = new THREE.DirectionalLight(0xfff2e6, .72);
  fillLight.position.set(-3.4, 2.8, 2.4);
  scene.add(fillLight, new THREE.HemisphereLight(0xffffff, 0xd9e1ea, 1.35));

  const floor = new THREE.Mesh(
    new THREE.CircleGeometry(2.12, 96),
    new THREE.MeshStandardMaterial({ color: 0x1c232c, roughness: .9, metalness: 0 }),
  );
  floor.rotation.x = -Math.PI / 2;
  floor.position.y = -.10;
  floor.receiveShadow = true;
  scene.add(floor);

  const modelRoot = new THREE.Group();
  scene.add(modelRoot);

  let foundation = null;
  let fixedPitchBracket = null;
  let headPivot = null;
  let yawAxis = null;
  let pitchAxis = null;
  let yawRotationAxis = "y";
  let targetYaw = 0;
  let targetPitch = 0;
  let poseDamping = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 1 : .24;
  let ledMaterials = [];
  let previewSource = "loading";
  let animationFrame = null;
  let officialModelRequested = false;
  let activeMount = document.querySelector('[data-screen="home"]:not([hidden])') ? "home" : "remote";
  let remoteVisible = !canvas.closest("[data-screen]")?.hidden;

  function makeBox(width, height, depth, material, x, y, z) {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(width, height, depth), material);
    mesh.position.set(x, y, z);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    return mesh;
  }

  function makeCircle(radius, material, x, y, z) {
    const mesh = new THREE.Mesh(new THREE.CircleGeometry(radius, 48), material);
    mesh.position.set(x, y, z);
    return mesh;
  }

  function createStackChanPreviewModel() {
    const group = new THREE.Group();
    const body = new THREE.Group();
    foundation = body;
    yawAxis = new THREE.Group();
    pitchAxis = new THREE.Group();
    headPivot = pitchAxis;
    headPivot.position.set(0, .92, 0);

    const shell = new THREE.MeshStandardMaterial({ color: 0xe1e4e7, roughness: .58, metalness: .06 });
    const darkShell = new THREE.MeshStandardMaterial({ color: 0x68717a, roughness: .66, metalness: .06 });
    const screen = new THREE.MeshStandardMaterial({ color: 0x070809, roughness: .34, metalness: .10 });
    const face = new THREE.MeshBasicMaterial({ color: 0xf1f5f9 });
    const accent = new THREE.MeshStandardMaterial({ color: 0xa8b0b8, roughness: .56, metalness: .08 });
    const side = new THREE.MeshStandardMaterial({ color: 0xb9bec6, roughness: .62, metalness: .06 });
    const baseDark = new THREE.MeshStandardMaterial({ color: 0x59616b, roughness: .68, metalness: .08 });
    const ledBlue = new THREE.MeshBasicMaterial({ color: 0x60a5fa });
    const ledPink = new THREE.MeshBasicMaterial({ color: 0xf472b6 });
    ledMaterials = [ledBlue, ledPink];

    const powerRing = new THREE.Mesh(
      new THREE.TorusGeometry(.07, .01, 12, 48),
      new THREE.MeshBasicMaterial({ color: 0x8b949e }),
    );
    powerRing.position.set(0, .39, .306);
    const leftLed = new THREE.Mesh(new THREE.SphereGeometry(.055, 24, 16), ledBlue);
    const rightLed = new THREE.Mesh(new THREE.SphereGeometry(.055, 24, 16), ledPink);
    leftLed.position.set(-.77, .13, .29);
    rightLed.position.set(.77, .13, .29);

    headPivot.add(
      makeBox(1.92, 1.54, .50, shell, 0, .80, 0),
      makeBox(.16, 1.46, .62, side, -1.04, .80, -.02),
      makeBox(.16, 1.46, .62, side, 1.04, .80, -.02),
      makeBox(1.90, .11, .58, side, 0, 1.61, -.02),
      makeBox(1.90, .11, .58, side, 0, -.01, -.02),
      makeBox(1.58, 1.26, .08, shell, 0, .80, -.31),
      makeBox(1.18, .045, .26, accent, 0, 1.69, -.02),
      makeBox(1.48, 1.18, .065, screen, 0, .80, .25),
      makeCircle(.06, face, -.34, .96, .292),
      makeCircle(.06, face, .34, .96, .292),
      makeBox(.30, .032, .018, face, 0, .74, .306),
      powerRing,
      leftLed,
      rightLed,
    );

    const neck = new THREE.Mesh(new THREE.CylinderGeometry(.24, .31, .22, 48), accent);
    neck.position.set(0, .88, 0);
    neck.castShadow = true;
    body.add(
      neck,
      makeBox(.82, .12, .58, side, 0, .76, 0),
      makeBox(1.22, .28, .90, shell, 0, .58, 0),
      makeBox(1.36, .20, .94, baseDark, 0, .35, 0),
      makeBox(1.18, .18, .86, darkShell, 0, .18, 0),
      makeBox(.55, .13, .88, baseDark, -.34, .03, 0),
      makeBox(.55, .13, .88, baseDark, .34, .03, 0),
    );
    yawAxis.add(pitchAxis);
    group.add(body, yawAxis);
    group.scale.setScalar(.78);
    group.position.y = .02;
    yawRotationAxis = "y";
    previewSource = "fallback";
    return group;
  }

  function setLocalTransformFromWorld(object, parent, worldMatrix) {
    parent.updateWorldMatrix(true, false);
    const localMatrix = parent.matrixWorld.clone().invert().multiply(worldMatrix);
    localMatrix.decompose(object.position, object.quaternion, object.scale);
    object.updateMatrixWorld(true);
  }

  function addExpressionPlane(head) {
    const faceCanvas = document.createElement("canvas");
    faceCanvas.width = 420;
    faceCanvas.height = 320;
    const context = faceCanvas.getContext("2d");
    context.fillStyle = "#08090a";
    context.fillRect(0, 0, 420, 320);
    context.fillStyle = "#f1f5f9";
    context.beginPath();
    context.arc(126, 126, 19, 0, Math.PI * 2);
    context.arc(294, 126, 19, 0, Math.PI * 2);
    context.fill();
    context.fillRect(164, 210, 92, 9);
    const texture = new THREE.CanvasTexture(faceCanvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.flipY = false;
    const plane = new THREE.Mesh(
      new THREE.PlaneGeometry(42, 32),
      new THREE.MeshBasicMaterial({ map: texture, side: THREE.DoubleSide }),
    );
    plane.position.set(0, 15.8, 0);
    plane.rotation.x = -Math.PI / 2;
    plane.rotation.z = Math.PI;
    head.add(plane);
  }

  function setupOfficialModel(model) {
    foundation = model.getObjectByName("_00_stackchan450_3");
    const centralComponent = model.getObjectByName("_00_stackchan450_2");
    const head = model.getObjectByName("_00_stackchan450_1");
    const headAssembly = model.getObjectByName("_00_stackchan450_1.001") || head;
    if (!foundation || !centralComponent || !head || !headAssembly) return false;

    ledMaterials = [];
    model.traverse((node) => {
      if (node.name === "plane" || node.isCamera || node.isLight) node.visible = false;
      if (!node.isMesh) return;
      node.castShadow = true;
      node.receiveShadow = true;
      const materials = Array.isArray(node.material) ? node.material : [node.material];
      materials.filter(Boolean).forEach((material) => {
        if (material.name === "MTL12" || material.name === "MTL12_001") ledMaterials.push(material);
      });
    });

    model.rotation.x = -Math.PI / 2;
    model.updateMatrixWorld(true);
    const initialBounds = new THREE.Box3().setFromObject(model);
    const largestDimension = Math.max(...initialBounds.getSize(new THREE.Vector3()).toArray(), 1);
    model.scale.setScalar(1.86 / largestDimension);
    model.updateMatrixWorld(true);
    const fittedBounds = new THREE.Box3().setFromObject(model);
    const fittedCenter = fittedBounds.getCenter(new THREE.Vector3());
    model.position.x -= fittedCenter.x;
    model.position.y += .02 - fittedBounds.min.y;
    model.position.z -= fittedCenter.z;
    model.updateMatrixWorld(true);

    const centralWorldMatrix = centralComponent.matrixWorld.clone();
    const headWorldMatrix = headAssembly.matrixWorld.clone();
    const foundationBounds = new THREE.Box3().setFromObject(foundation);
    const centralBoundsCenter = new THREE.Box3().setFromObject(centralComponent).getCenter(new THREE.Vector3());
    const pitchPivotWorld = centralComponent.getWorldPosition(new THREE.Vector3());
    pitchPivotWorld.z = centralBoundsCenter.z;
    const yawPivotWorld = new THREE.Vector3(
      pitchPivotWorld.x,
      foundationBounds.max.y,
      pitchPivotWorld.z,
    );

    yawAxis = new THREE.Group();
    yawAxis.name = "yawAxis";
    modelRoot.add(yawAxis);
    yawAxis.position.copy(modelRoot.worldToLocal(yawPivotWorld.clone()));
    yawAxis.add(centralComponent);
    setLocalTransformFromWorld(centralComponent, yawAxis, centralWorldMatrix);

    const fixedPitchAxle = new THREE.Object3D();
    fixedPitchAxle.name = "fixedPitchAxle";
    fixedPitchAxle.position.copy(yawAxis.worldToLocal(pitchPivotWorld.clone()));
    yawAxis.add(fixedPitchAxle);
    fixedPitchBracket = fixedPitchAxle;

    pitchAxis = new THREE.Group();
    pitchAxis.name = "pitchAxis";
    yawAxis.add(pitchAxis);
    pitchAxis.position.copy(yawAxis.worldToLocal(pitchPivotWorld.clone()));
    pitchAxis.add(headAssembly);
    setLocalTransformFromWorld(headAssembly, pitchAxis, headWorldMatrix);
    headPivot = head;
    addExpressionPlane(head);

    yawRotationAxis = "y";
    previewSource = "official-glb";
    return true;
  }

  function setPose(yaw, pitch) {
    targetYaw = THREE.MathUtils.degToRad(THREE.MathUtils.clamp(Number(yaw) || 0, -128, 128));
    const physicalPitch = THREE.MathUtils.clamp(Number(pitch) || 6, 3, 87);
    targetPitch = THREE.MathUtils.degToRad(-(physicalPitch - 6));
  }

  function setLedColor(red, green, blue) {
    const color = new THREE.Color(red / 255, green / 255, blue / 255);
    ledMaterials.forEach((material) => {
      if (material.color) material.color.copy(color);
      if (material.emissive) material.emissive.copy(color);
      material.needsUpdate = true;
    });
  }

  function setMotionSpeed(level) {
    poseDamping = [0.10, 0.16, 0.24, 0.34][THREE.MathUtils.clamp(Number(level) || 0, 0, 3)];
  }

  function getDebugState() {
    scene.updateMatrixWorld(true);
    const foundationMatrix = foundation ? foundation.matrixWorld.elements.map((value) => Number(value.toFixed(6))) : [];
    const pitchPivotPosition = pitchAxis ? pitchAxis.getWorldPosition(new THREE.Vector3()) : new THREE.Vector3();
    const fixedPitchAxlePosition = fixedPitchBracket
      ? fixedPitchBracket.getWorldPosition(new THREE.Vector3())
      : new THREE.Vector3();
    const pitchAxleGap = fixedPitchBracket && pitchAxis
      ? fixedPitchAxlePosition.distanceTo(pitchPivotPosition)
      : 0;
    return {
      source: previewSource,
      yaw: THREE.MathUtils.radToDeg(yawAxis?.rotation[yawRotationAxis] || 0),
      pitch: THREE.MathUtils.radToDeg(pitchAxis?.rotation.x || 0),
      foundationMatrix,
      pitchPivotPosition: pitchPivotPosition.toArray().map((value) => Number(value.toFixed(6))),
      fixedPitchAxlePosition: fixedPitchAxlePosition.toArray().map((value) => Number(value.toFixed(6))),
      pitchAxleGap: Number(pitchAxleGap.toFixed(6)),
      cameraZ: Number(camera.position.z.toFixed(3)),
      cameraAspect: Number(camera.aspect.toFixed(3)),
      viewport: [canvas.clientWidth, canvas.clientHeight],
    };
  }

  window.stackChan3DPreview = { setPose, setLedColor, setMotionSpeed, getDebugState };
  setPose(canvas.dataset.yaw, canvas.dataset.pitch);
  window.dispatchEvent(new Event("stackchan3dready"));

  function resize() {
    const bounds = canvas.getBoundingClientRect();
    const width = Math.max(1, Math.floor(bounds.width));
    const height = Math.max(1, Math.floor(bounds.height));
    if (canvas.width === width && canvas.height === height) return;
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.position.z = 6.5 * Math.max(1, .78 / camera.aspect) * (activeMount === "home" ? 1.12 : 1);
    camera.updateProjectionMatrix();
  }

  new ResizeObserver(resize).observe(canvas);
  function frame() {
    animationFrame = null;
    if (!remoteVisible || document.visibilityState !== "visible") return;
    resize();
    if (yawAxis) yawAxis.rotation[yawRotationAxis] += (targetYaw - yawAxis.rotation[yawRotationAxis]) * poseDamping;
    if (pitchAxis) pitchAxis.rotation.x += (targetPitch - pitchAxis.rotation.x) * poseDamping;
    renderer.render(scene, camera);
    animationFrame = requestAnimationFrame(frame);
  }

  function startRendering() {
    if (animationFrame !== null || !remoteVisible || document.visibilityState !== "visible") return;
    animationFrame = requestAnimationFrame(frame);
  }

  function stopRendering() {
    if (animationFrame === null) return;
    cancelAnimationFrame(animationFrame);
    animationFrame = null;
  }

  function mountPreview(target) {
    const mount = target === "home" ? homeMount : target === "remote" ? remoteMount : null;
    activeMount = target;
    remoteVisible = Boolean(mount);
    if (!mount) {
      stopRendering();
      return;
    }
    if (canvas.parentElement !== mount) mount.append(canvas, fallback);
    loadOfficialModel();
    startRendering();
  }

  window.addEventListener("stackchanremoteshow", () => {
    remoteVisible = true;
    loadOfficialModel();
    startRendering();
  });
  window.addEventListener("stackchanremotehide", () => {
    remoteVisible = false;
    stopRendering();
  });
  window.addEventListener("stackchanscreenchange", (event) => mountPreview(event.detail?.target));
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") startRendering();
    else stopRendering();
  });

  function useFallbackModel() {
    modelRoot.add(createStackChanPreviewModel());
    setPose(canvas.dataset.yaw, canvas.dataset.pitch);
    setLedColor(96, 165, 250);
    fallback.textContent = "已切换到兼容 3D 模型";
  }

  function loadOfficialModel() {
    if (officialModelRequested) return;
    officialModelRequested = true;
    new GLTFLoader().load("/model-assets/stack_chan_model.glb", (gltf) => {
      const model = gltf.scene;
      modelRoot.add(model);
      if (!setupOfficialModel(model)) {
        modelRoot.remove(model);
        useFallbackModel();
        return;
      }
      setPose(canvas.dataset.yaw, canvas.dataset.pitch);
      setLedColor(255, 224, 170);
      fallback.textContent = "实体同源 3D 模型已加载";
      window.setTimeout(() => { fallback.style.opacity = "0"; }, 1200);
    }, undefined, useFallbackModel);
  }

  // 页面可能直接落在对话页；3D 预览只挂到当前可见的那一屏。
  const initialScreen = [...document.querySelectorAll("[data-screen]")].find((screen) => !screen.hidden)?.dataset.screen || "remote";
  mountPreview(initialScreen);
}
