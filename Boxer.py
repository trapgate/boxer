# Author-Geoff Hickey
# Description-Creates finger-jointed boxes suitable for laser cutters.

import adsk.core
import adsk.fusion
import adsk.cam
import traceback
import math

# TODO:
# - Make the finger-joint edge into a standalone command.
# - Temporarily display the origin when the command window is taking input.

# Global list to keep all event handlers in scope.
handlers = []

app = None
ui = None


# BoxerInputs is used to hold the parameters specified by the user for creating
# a box.
class boxerInputs:
    pass


def run(context):
    try:
        global app, ui
        app = adsk.core.Application.get()
        ui = app.userInterface

        cmdDefs = ui.commandDefinitions
        buttonBoxer = cmdDefs.addButtonDefinition(
            'BoxerButtonDefId',
            'Finger-Jointed Box',
            ("Insert a finger-jointed box into the design. The box will be "
             "inserted as a new component. These boxes can be cut with a laser "
             "cutter or similar tool."),
            './Resources')

        buttonCreated = BoxerCommandCreatedHandler()
        buttonBoxer.commandCreated.add(buttonCreated)
        handlers.append(buttonCreated)

        createPanel = ui.allToolbarPanels.itemById('SolidCreatePanel')

        buttonControl = createPanel.controls.addCommand(buttonBoxer)

    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


def stop(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface

        cmdDef = ui.commandDefinitions.itemById('BoxerButtonDefId')
        if cmdDef:
            cmdDef.deleteMe()

        createPanel = ui.allToolbarPanels.itemById('SolidCreatePanel')
        cntrl = createPanel.controls.itemById('BoxerButtonDefId')
        if cntrl:
            cntrl.deleteMe()

    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


class BoxerCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            eventArgs = adsk.core.CommandCreatedEventArgs.cast(args)
            cmd = eventArgs.command
            des = adsk.fusion.Design.cast(app.activeProduct)
            unitsMgr = des.unitsManager
            lenUnit = unitsMgr.defaultLengthUnits

            # Command inputs
            inputs = cmd.commandInputs

            # This control let the user specify a construction plane to build
            # the box on, but that introduces some corner cases, and it's not
            # obviously valuable, since the box can just be moved after it's
            # built.
            # plane = inputs.addSelectionInput(
            #     'plane', 'Plane', 'select plane, planar face, or sketch profile for the base')
            # plane.addSelectionFilter('PlanarFaces')
            # plane.addSelectionFilter('ConstructionPlanes')

            lid = inputs.addBoolValueInput('lid', 'Add a lid', True)
            lid.tooltip = ("If this option is selected, a lid will be generated "
                           "for the box. The lid will be finger-jointed to the "
                           "sides it touches.")

            length = inputs.addValueInput(
                'baseLength', 'Box length', lenUnit, adsk.core.ValueInput.createByReal(0))
            length.tooltip = ("Enter the length of the box along the X-axis")

            width = inputs.addValueInput(
                'baseWidth', 'Box width', lenUnit, adsk.core.ValueInput.createByReal(0))
            width.tooltip = ("Enter the width of the box along the Y-axis")

            height = inputs.addValueInput(
                'height', 'Box Height', lenUnit, adsk.core.ValueInput.createByReal(0))
            height.tooltip = ("Enter the height of the box along the Z-axis")

            radioInOutGroup = inputs.addRadioButtonGroupCommandInput(
                'dimsInOut', 'Dimensions are')
            radioItems = radioInOutGroup.listItems
            radioItems.add("outer", True)
            radioItems.add("inner", False)

            thickness = inputs.addValueInput(
                'thickness', 'Material thickness', lenUnit, adsk.core.ValueInput.createByReal(0))
            thickness.tooltip = ("Enter the exact thickness of the material here. "
                                 "The same thickness is used for all sides of the "
                                 "box.")
            fingerScale = inputs.addIntegerSliderCommandInput(
                'fingerScale', 'Finger scale', 1, 20)
            fingerScale.valueOne = 5
            fingerScale.tooltip = ("The finger size is set as a multiple of the "
                                   "material thickness. The exact size of the "
                                   "fingers will be adjusted before drawing so "
                                   "that there are at least 3 fingers per side.")

            fingerInfo = inputs.addTextBoxCommandInput(
                'fingerInfo', '', "", 2, True)

            # Connect to the validate inputs event
            onValidate = BoxerCommandValidateHandler()
            cmd.validateInputs.add(onValidate)
            handlers.append(onValidate)

            # Connect to the execute preview event
            onPreview = BoxerCommandPreviewHandler()
            cmd.executePreview.add(onPreview)
            handlers.append(onPreview)

            # Connect to the execute event
            onExecute = BoxerCommandExecuteHandler()
            cmd.execute.add(onExecute)
            handlers.append(onExecute)

            # Connect to the inputChanged event
            onInputChanged = BoxerCommandInputChangedHandler()
            cmd.inputChanged.add(onInputChanged)
            handlers.append(onInputChanged)

        except:
            ui.messageBox('Boxer failed:\n{}'.format(
                traceback.format_exc()))


class BoxerCommandValidateHandler(adsk.core.ValidateInputsEventHandler):
    """Handler for checking whether parameters are valid"""

    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            vArgs = adsk.core.ValidateInputsEventArgs.cast(args)
            inputs = getInputs(vArgs.inputs, writeBack=True)
            if inputs.plane is None:
                vArgs.areInputsValid = False
            if inputs.thickness == 0:
                vArgs.areInputsValid = False
            for dim in [inputs.length, inputs.width, inputs.height]:
                if dim <= 2*inputs.thickness:
                    vArgs.areInputsValid = False
        except:
            ui.messageBox('Boxer failed:\n{}'.format(traceback.format_exc()))


class BoxerCommandInputChangedHandler(adsk.core.InputChangedEventHandler):
    """Handler for changed inputs"""

    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            # If a thickness is set, calculate & display the approximate width
            # of the fingers.
            eventArgs = adsk.core.InputChangedEventArgs.cast(args)
            inp = eventArgs.inputs
            inputs = getInputs(inp)
            fingerInfo = inp.itemById('fingerInfo')
            if inputs.thickness > 0:
                des = adsk.fusion.Design.cast(app.activeProduct)
                unitsMgr = des.unitsManager
                target = unitsMgr.formatInternalValue(
                    inputs.fingerScale * inputs.thickness,
                    unitsMgr.defaultLengthUnits,
                    True)
                fingerInfo.formattedText = 'Fingers will be about {}'.format(
                    target)
            else:
                fingerInfo.formattedText = ''
        except:
            ui.messageBox('Boxer failed:\n{}'.format(traceback.format_exc()))


class BoxerCommandPreviewHandler(adsk.core.CommandEventHandler):
    """Handler for the preview event"""

    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            eventArgs = adsk.core.CommandEventArgs.cast(args)
            inp = eventArgs.command.commandInputs
            inputs = getInputs(inp)
            drawBox(inputs)
            eventArgs.isValidResult = True
        except:
            ui.messageBox('Boxer preview failed:\n{}'.format(
                traceback.format_exc()))


class BoxerCommandExecuteHandler(adsk.core.CommandEventHandler):
    """Handler for the execute event"""

    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            eventArgs = adsk.core.CommandEventArgs.cast(args)
            inp = eventArgs.command.commandInputs
            inputs = getInputs(inp)
            drawBox(inputs)
        except:
            if ui:
                ui.messageBox('Boxer failed:\n{}'.format(
                    traceback.format_exc()))


def getInputs(inputs, writeBack=False):
    """getInputs pulls all the inputs from the dialog and returns them in a 
    struct. There's a wrinkle here: when you read from value inputs, it causes
    the screen to update the displayed value so that it includes the units. This
    is...more than slightly annoying - if you don't type fast enough, the
    validate handler gets called, reads all the inputs, and bumps your curson to
    the end of the value entry, after the units. To suppress that behavior, the
    validate handler passes 'writeBack=True' to this routine, which causes it to
    write the value back to the control right after reading it.
    """
    inp = boxerInputs()

    des = adsk.fusion.Design.cast(app.activeProduct)
    plane = des.rootComponent.xZConstructionPlane
    # The plane selection control is currently commented out, and all boxes are
    # constructed on the root component's XZ plane.
    inp.plane = plane
    # inp.plane = inputs.itemById('plane').selection(0).entity
    inp.drawLid = inputs.itemById('lid').value
    inp.length = readInputValue(inputs.itemById('baseLength'), writeBack)
    inp.width = readInputValue(inputs.itemById('baseWidth'), writeBack)
    inp.height = readInputValue(inputs.itemById('height'), writeBack)
    inp.thickness = readInputValue(inputs.itemById('thickness'), writeBack)
    inp.fingerScale = inputs.itemById('fingerScale').valueOne

    inp.dimsOuter = inputs.itemById(
        'dimsInOut').selectedItem.name == "outer"

    return inp


def readInputValue(item, writeBack=False):
    """Reads a value from an input control. If writeBack is True, it writes the
    value back again immediately, to prevent the display from updating to add
    the units (and move the cursor).
    """
    v = item.value
    if writeBack:
        item.value = v
    return v


def drawBox(inputs):
    """drawBox creates the finger-jointed box.
    """
    app = adsk.core.Application.get()
    ui = app.userInterface
    des = adsk.fusion.Design.cast(app.activeProduct)

    length = inputs.length
    width = inputs.width
    height = inputs.height
    thickness = inputs.thickness
    drawLid = inputs.drawLid
    fingerScale = inputs.fingerScale

    # If the user gave us inner dimensions, adjust them so they're outer
    # dimensions.
    if not inputs.dimsOuter:
        length += 2*thickness
        width += 2*thickness
        height += thickness
        if drawLid:
            height += thickness

    # Create the box as a new component
    root = des.rootComponent
    transform = adsk.core.Matrix3D.create()
    boxComponent = root.occurrences.addNewComponent(transform)
    sk = boxComponent.component.sketches.addWithoutEdges(inputs.plane)
    extrudes = boxComponent.component.features.extrudeFeatures
    lines = sk.sketchCurves.sketchLines
    combines = boxComponent.component.features.combineFeatures

    # base
    p1 = adsk.core.Point3D.create(thickness, thickness, 0)
    p2 = adsk.core.Point3D.create(length-thickness, width-thickness, 0)
    base = lines.addTwoPointRectangle(p1, p2)

    # fingers for the y axis edges
    fingers = fingersForY(calcFingers2D(width, thickness, factor=fingerScale))
    sketchFingers(lines, fingers, length-thickness, 0)

    # fingers for the x axis edges
    fingers = fingersForX(calcFingers2D(length, thickness, factor=fingerScale))
    sketchFingers(lines, fingers, 0, width-thickness)

    newBody = adsk.fusion.FeatureOperations.NewBodyFeatureOperation

    # extrude the base
    prof = adsk.core.ObjectCollection.create()
    for p in sk.profiles:
        prof.add(p)
    dist = adsk.core.ValueInput.createByReal(thickness)
    baseBody = extrudeSide(extrudes, "base", prof, thickness, 0.0)

    # extrude the lid
    lidBody = None
    if drawLid:
        lidBody = extrudeSide(
            extrudes, "lid", prof, -thickness, height)

    # FIXME: This method doesn't work on inclined planes. The front and
    # side sketches end up offset by some amount from the origin of the
    # first sketch, because the plane the first sketch is on probably
    # won't intersect with the workspace origin.
    frontFace = None
    sideFace = None
    for f in baseBody.faces:
        p = sk.modelToSketchSpace(f.pointOnFace)
        if math.fabs(p.y) < app.pointTolerance:
            frontFace = f
        if math.fabs(p.x) < app.pointTolerance:
            sideFace = f
        if frontFace and sideFace:
            break
    if frontFace is None:
        raise Exception('failed to find front face on base body')
    if sideFace is None:
        raise Exception(
            'failed to find right/left side face on base body')

    # sketch the front/back
    frontSk = boxComponent.component.sketches.addWithoutEdges(
        frontFace)
    lines = frontSk.sketchCurves.sketchLines

    p1 = adsk.core.Point3D.create(thickness, 0, 0)
    p2 = adsk.core.Point3D.create(length-thickness, height, 0)
    lines.addTwoPointRectangle(p1, p2)
    fingers = fingersForY(calcFingers2D(height, thickness, factor=fingerScale))
    sketchFingers(lines, fingers, length-thickness, 0)

    # sketch the left/right sides
    sideSk = boxComponent.component.sketches.addWithoutEdges(sideFace)
    lines = sideSk.sketchCurves.sketchLines

    p1 = adsk.core.Point3D.create(0, 0, 0)
    p2 = adsk.core.Point3D.create(-width, height, 0)
    lines.addTwoPointRectangle(p1, p2)

    # extrude front back and sides
    prof = adsk.core.ObjectCollection.create()
    for p in frontSk.profiles:
        prof.add(p)
    frontBody = extrudeSide(extrudes, "front", prof, -thickness, 0.0)
    backBody = extrudeSide(
        extrudes, "back", prof, thickness, -width)

    prof = adsk.core.ObjectCollection.create()
    for p in sideSk.profiles:
        prof.add(p)
    leftBody = extrudeSide(extrudes, "left", prof, -thickness, 0.0)
    rightBody = extrudeSide(
        extrudes, "right", prof, thickness, -length)

    # Combine the sides
    tools = adsk.core.ObjectCollection.create()
    tools.add(frontBody)
    tools.add(backBody)
    tools.add(baseBody)
    if drawLid:
        tools.add(lidBody)

    for side in [leftBody, rightBody]:
        combineInp = combines.createInput(side, tools)
        combineInp.isKeepToolBodies = True
        combineInp.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
        combines.add(combineInp)

    tools = adsk.core.ObjectCollection.create()
    tools.add(baseBody)
    if drawLid:
        tools.add(lidBody)
    for side in [frontBody, backBody, leftBody, rightBody]:
        if side is None:
            continue
        combineInp = combines.createInput(side, tools)
        combineInp.isKeepToolBodies = True
        combineInp.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
        combines.add(combineInp)


def extrudeSide(extrudes, name, prof, thickness, offset):
    extentDir = adsk.fusion.ExtentDirections.PositiveExtentDirection
    if thickness < 0:
        extentDir = adsk.fusion.ExtentDirections.NegativeExtentDirection
    dist = adsk.core.ValueInput.createByReal(math.fabs(thickness))
    newBody = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    offDist = adsk.core.ValueInput.createByReal(offset)
    startOffs = adsk.fusion.OffsetStartDefinition.create(offDist)
    extent = adsk.fusion.DistanceExtentDefinition.create(dist)
    inp = extrudes.createInput(prof, newBody)
    inp.setOneSideExtent(extent, extentDir)
    inp.startExtent = startOffs
    solid = extrudes.add(inp)
    body = solid.bodies.item(0)
    body.name = name
    return body


def fingersForX(fingers):
    xFingers = []
    for f in fingers:
        p1, p2 = f
        p1.x, p1.y = p1.y, p1.x
        p2.x, p2.y = p2.y, p2.x
        xFingers.append((p1, p2))
    return xFingers


def fingersForY(fingers):
    return fingers


def sketchFingers(lines, fingers, xOffs, yOffs):
    """Draws a set of fingers in a sketch"""
    vect = adsk.core.Vector3D.create(xOffs, yOffs, 0)
    for f in fingers:
        p1, p2 = f
        lines.addTwoPointRectangle(p1, p2)
        p1.translateBy(vect)
        p2.translateBy(vect)
        lines.addTwoPointRectangle(p1, p2)


def fingerJointEdge(component: adsk.fusion.Component,
                    body1: adsk.fusion.BRepBody,
                    body2: adsk.fusion.BRepBody):
    """Add finger joints to an edge between two bodies. The edges must
    intersect."""
    if body2 is None:
        return
    # Find the face on body1 that's completely contained by any face on body2.
    fingerEdge = None
    for face in body1.faces:
        bbox = face.boundingBox
        for cf in body2.faces:
            cbbox = cf.boundingBox
            if cbbox.contains(bbox.minPoint) and cbbox.contains(bbox.maxPoint):
                fingerEdge = face
                break
        if fingerEdge is not None:
            break

    if fingerEdge is None:
        raise Exception('failed to find common edge for bodies')

    # Create a sketch for the fingers
    sk = component.sketches.add(fingerEdge)

    # The new sketch contains the projected profile of the end of the side,
    # which is a rectangle, but may be located some distance from the origin.
    # Find its extents, so that we can use its lower left corner as the origin
    # for the fingers we're going to draw.
    firstPoint = sk.sketchCurves.sketchLines.item(0).startSketchPoint.geometry
    minVect = adsk.core.Vector3D.create(
        firstPoint.x, firstPoint.y, firstPoint.z)
    maxVect = adsk.core.Vector3D.create(
        firstPoint.x, firstPoint.y, firstPoint.z)
    for line in sk.sketchCurves:
        line.isConstruction = True
        for point in [line.startSketchPoint, line.endSketchPoint]:
            minVect.x = min(minVect.x, point.geometry.x)
            maxVect.x = max(maxVect.x, point.geometry.x)
            minVect.y = min(minVect.y, point.geometry.y)
            maxVect.y = max(maxVect.y, point.geometry.y)
            minVect.z = min(minVect.z, point.geometry.z)
            maxVect.z = max(maxVect.z, point.geometry.z)

    edgeX = maxVect.x - minVect.x
    edgeY = maxVect.y - minVect.y

    thickness = min(edgeX, edgeY)

    # Get an array of fingers to draw
    fingers = calcFingers(edgeX, edgeY)

    lines = sk.sketchCurves.sketchLines
    extrudes = component.features.extrudeFeatures

    faces = []
    for f in fingers:
        p1, p2 = f
        p1.translateBy(minVect)
        p2.translateBy(minVect)
        faces.append(lines.addTwoPointRectangle(p1, p2))

    prof = adsk.core.ObjectCollection.create()
    for pr in sk.profiles:
        prof.add(pr)
    dist = adsk.core.ValueInput.createByReal(thickness)
    extent = adsk.fusion.DistanceExtentDefinition.create(dist)
    inp = extrudes.createInput(
        prof, adsk.fusion.FeatureOperations.CutFeatureOperation)
    inp.participantBodies = [body1]
    inp.setOneSideExtent(
        extent, adsk.fusion.ExtentDirections.NegativeExtentDirection)
    extrudes.add(inp)


def calcFingers2D(edgeLen: float, thickness: float, factor=5):
    """Calculate fingers for an edge. This routine will generate fingers about
    5x longer than the material thickness, and will always generate an odd 
    number of fingers (just because I think that looks better). The fingers will
    be centered on the edge being jointed. This routine will generate fingers
    along whichever of the two edges passed into it is longer - the shorter edge
    will be used as the material thickness. The factor sets the desired finger
    length as a multiple of the material thickness. This is a goal only; if an
    edge is too short to allow this, this routine will calculate a smaller
    factor to use, down to a minimum of 1.
    """
    fingers = []

    if 3 * thickness > edgeLen:
        return []
    flen = factor * thickness
    fcount = math.floor(edgeLen/flen)
    while fcount == 0:
        factor -= 1
        if factor == 0:
            return []
        flen = factor * thickness
        fcount = math.floor(edgeLen/flen)
    if fcount < 3:
        # shorten the fingers so there are at least 3.
        flen = edgeLen / 3
        fcount = math.floor(edgeLen/flen)
    if fcount % 2 == 0:
        # lengthen the fingers so there's one less
        flen += flen/fcount
        fcount = math.floor(edgeLen/flen)

    y = (edgeLen - fcount * flen) / 2
    for i in range(fcount):
        if i % 2 == 1:
            p1 = adsk.core.Point3D.create(0, y, 0)
            p2 = adsk.core.Point3D.create(thickness, y + flen, 0)
            fingers.append((p1, p2))
        y += flen
    return fingers


def calcFingers(edgeX: float, edgeY: float):
    if edgeX > edgeY:
        edgeLen, thickness = edgeX, edgeY
    else:
        edgeLen, thickness = edgeY, edgeX

    # This point generating routine figures out which dimension is which.
    def point(x, y):
        if edgeX > edgeY:
            return adsk.core.Point3D.create(y, x, 0)
        else:
            return adsk.core.Point3D.create(x, y, 0)
    fingers = []

    innerHeight = edgeLen - thickness * 2

    # we'll create fingers about the length of 8 * the thickness of the stock.
    flen = 8 * thickness
    fcount = math.floor(innerHeight/flen)
    if fcount == 0:
        raise ValueError('edge is too short for finger joints')
    if fcount < 3:
        # shorten the fingers so there are at least 3.
        flen = innerHeight / 3
        fcount = math.floor(innerHeight/flen)
    if fcount % 2 == 0:
        # lengthen the fingers so there's one less.
        flen += flen/fcount
        fcount = math.floor(innerHeight/flen)

    y = (edgeLen - fcount * flen) / 2
    for i in range(fcount):
        if i % 2 == 1:
            p1 = point(0, y)
            p2 = point(thickness, y + flen)
            fingers.append((p1, p2))
        y += flen

    return fingers


def findContainedProfiles(lines):
    """Find the profiles contained within a collection of lines. This is done by
    creating a bouding box for the lines, and then returning a list of the 
    sketch profiles that fall within that bounding box."""
    sk = lines.item(0).parentSketch

    bbox = lines[0].boundingBox.copy()
    for line in lines:
        bbox.combine(line.boundingBox)
    return findContainedProfilesBBox(sk, bbox)


def findContainedProfilesBBox(sketch, bbox):
    """Find the profiles contained within a bouding box. This routine works by
    iterating through all the profiles in the sketch, and checking if the
    bounding box for the profile is contained within the bounding box passed in
    to this routine. Because bounding boxes in practice are often slightly 
    larger than the geometry they contain, this routine first shrinks the bbox 
    it's checking slightly. This is a hack, but has worked so far."""
    prs = sketch.profiles

    rProfiles = adsk.core.ObjectCollection.create()
    # vectors used to adjust the bbox around the profile. See below.
    lowVec = adsk.core.Vector3D.create(
        app.pointTolerance, app.pointTolerance, 0.0)
    highVec = adsk.core.Vector3D.create(-app.pointTolerance, -
                                        app.pointTolerance, 0.0)
    for pr in prs:
        # Bounding boxes are not exact enough for our purposes - the max value
        # of the box for profiles is frequently outside of the bounding box
        # defined by the lines use to create the profile. For now, compensate
        # by shrinking the profile's bounding box by the pointTolerance value.
        # This is not a correct solution.
        minP = pr.boundingBox.minPoint.copy()
        minP.translateBy(lowVec)
        maxP = pr.boundingBox.maxPoint.copy()
        maxP.translateBy(highVec)
        if bbox.contains(minP) and bbox.contains(maxP):
            rProfiles.add(pr)
            continue

    return rProfiles
