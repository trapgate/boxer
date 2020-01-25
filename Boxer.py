# Author-Geoff Hickey
# Description-Creates finger-jointed boxes suitable for laser cutters.

import adsk.core
import adsk.fusion
import adsk.cam
import traceback
import math

# TODO:
# - Build only 3 sides, and mirror?
# - Make the finger-joint edge into a standalone command.
# - Add finger control
# - Temporarily display the origin when the command window is taking input.

# Global list to keep all event handlers in scope.
handlers = []

app = None
ui = None


def run(context):
    try:
        global app, ui
        app = adsk.core.Application.get()
        ui = app.userInterface

        cmdDefs = ui.commandDefinitions
        buttonBoxer = cmdDefs.addButtonDefinition(
            'BoxerButtonDefId',
            'Create Finger-jointed box',
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

            # TODO: Add tooltips
            # TODO: Turn on the lightbulb for the origin?
            plane = inputs.addSelectionInput(
                'plane', 'Plane', 'select plane, planar face, or sketch profile for the base')
            plane.addSelectionFilter('PlanarFaces')
            plane.addSelectionFilter('ConstructionPlanes')
            plane.addSelectionFilter('Profiles')

            lid = inputs.addBoolValueInput('lid', 'Add a lid', True)
            lid.tooltip = ("If this option is selected, a lid will be generated "
                           "for the box. The lid will be finger-jointed to the "
                           "sides it touches.")

            length = inputs.addValueInput(
                'baseLength', 'Box length', lenUnit, adsk.core.ValueInput.createByReal(0))

            width = inputs.addValueInput(
                'baseWidth', 'Box width', lenUnit, adsk.core.ValueInput.createByReal(0))

            height = inputs.addValueInput(
                'height', 'Box Height', lenUnit, adsk.core.ValueInput.createByReal(0))

            radioInOutGroup = inputs.addRadioButtonGroupCommandInput(
                'dimsInOut', 'Dimensions are')
            radioItems = radioInOutGroup.listItems
            radioItems.add("outer", True)
            radioItems.add("inner", False)

            thickness = inputs.addValueInput(
                'thickness', 'Material thickness', lenUnit, adsk.core.ValueInput.createByReal(0))

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


class BoxerCommandInputChangedHandler(adsk.core.InputChangedEventHandler):
    """Handler for changed inputs"""

    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            eventArgs = adsk.core.InputChangedEventArgs.cast(args)
            inputs = eventArgs.inputs
            cmdInput = eventArgs.input

            # does nothing yet
            # TODO: Validate inputs
            # TODO: Preview?

        except:
            ui.messageBox('Boxer failed:\n{}'.format(traceback.format_exc()))


class BoxerCommandExecuteHandler(adsk.core.CommandEventHandler):
    """Handler for the execute event"""

    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            eventArgs = adsk.core.CommandEventArgs.cast(args)

            app = adsk.core.Application.get()
            ui = app.userInterface
            des = adsk.fusion.Design.cast(app.activeProduct)

            inputs = eventArgs.command.commandInputs
            plane = inputs.itemById('plane').selection(0).entity
            drawLid = inputs.itemById('lid').value
            length = inputs.itemById('baseLength').value
            width = inputs.itemById('baseWidth').value
            height = inputs.itemById('height').value
            thickness = inputs.itemById('thickness').value

            dimsOuter = inputs.itemById('dimsInOut').selectedItem == "outer"
            # If the user gave us inner dimensions, adjust them so they're outer
            # dimensions.
            if not dimsOuter:
                length += 2*thickness
                width += 2*thickness
                height += thickness
                if drawLid:
                    height += thickness

            # Create the box as a new component
            root = des.rootComponent
            transform = adsk.core.Matrix3D.create()
            markerStart = des.timeline.markerPosition
            boxComponent = root.occurrences.addNewComponent(transform)
            sk = boxComponent.component.sketches.add(plane)
            extrudes = boxComponent.component.features.extrudeFeatures
            lines = sk.sketchCurves.sketchLines
            combines = boxComponent.component.features.combineFeatures

            # base
            p1 = adsk.core.Point3D.create(0, 0, 0)
            p2 = adsk.core.Point3D.create(
                length, width, 0)
            base = lines.addTwoPointRectangle(p1, p2)

            # sides
            p2 = adsk.core.Point3D.create(length, thickness, 0)
            front = lines.addTwoPointRectangle(p1, p2)
            p1 = adsk.core.Point3D.create(0, width, 0)
            p2 = adsk.core.Point3D.create(length, width-thickness, 0)
            back = lines.addTwoPointRectangle(p1, p2)
            p1 = adsk.core.Point3D.create(0, 0, 0)
            p2 = adsk.core.Point3D.create(thickness, width, 0)
            left = lines.addTwoPointRectangle(p1, p2)
            p1 = adsk.core.Point3D.create(length-thickness, 0, 0)
            p2 = adsk.core.Point3D.create(length, width, 0)
            right = lines.addTwoPointRectangle(p1, p2)

            newBody = adsk.fusion.FeatureOperations.NewBodyFeatureOperation

            # extrude the sides
            prof = findContainedProfiles(base)
            dist = adsk.core.ValueInput.createByReal(thickness)
            baseSolid = extrudes.addSimple(prof, dist, newBody)
            baseSolid.bodies.item(0).name = "base"

            lidBody = None
            if drawLid:
                offDist = adsk.core.ValueInput.createByReal(height)
                startOffs = adsk.fusion.OffsetStartDefinition.create(offDist)
                extent = adsk.fusion.DistanceExtentDefinition.create(dist)
                inp = extrudes.createInput(prof, newBody)
                inp.setOneSideExtent(
                    extent, adsk.fusion.ExtentDirections.NegativeExtentDirection)
                inp.startExtent = startOffs
                lidSolid = extrudes.add(inp)
                lidBody = lidSolid.bodies.item(0)
                lidBody.name = "lid"

            prof = findContainedProfiles(left)
            dist = adsk.core.ValueInput.createByReal(height)
            leftSolid = extrudes.addSimple(prof, dist, newBody)
            leftSolid.bodies.item(0).name = "left"

            prof = findContainedProfiles(right)
            rightSolid = extrudes.addSimple(prof, dist, newBody)
            rightSolid.bodies.item(0).name = "right"

            prof = findContainedProfiles(front)
            frontSolid = extrudes.addSimple(prof, dist, newBody)
            frontSolid.bodies.item(0).name = "front"

            prof = findContainedProfiles(back)
            backSolid = extrudes.addSimple(prof, dist, newBody)
            backSolid.bodies.item(0).name = "back"

            baseBody = baseSolid.bodies.item(0)
            frontBody = frontSolid.bodies.item(0)
            backBody = backSolid.bodies.item(0)
            leftBody = leftSolid.bodies.item(0)
            rightBody = rightSolid.bodies.item(0)

            # Now we have a set of interfering sides. Compute the fingers and
            # add/subtract them from the appropriate edges.
            fingerJointEdge(boxComponent.component, frontBody, leftBody)
            fingerJointEdge(boxComponent.component, frontBody, rightBody)
            fingerJointEdge(boxComponent.component, frontBody, baseBody)
            fingerJointEdge(boxComponent.component, frontBody, lidBody)

            fingerJointEdge(boxComponent.component, leftBody, baseBody)
            fingerJointEdge(boxComponent.component, leftBody, lidBody)

            fingerJointEdge(boxComponent.component, rightBody, baseBody)
            fingerJointEdge(boxComponent.component, rightBody, lidBody)

            fingerJointEdge(boxComponent.component, backBody, leftBody)
            fingerJointEdge(boxComponent.component, backBody, rightBody)
            fingerJointEdge(boxComponent.component, backBody, baseBody)
            fingerJointEdge(boxComponent.component, backBody, lidBody)

            # Combine the sides
            tools = adsk.core.ObjectCollection.create()
            tools.add(frontBody)
            tools.add(backBody)

            for side in [leftBody, rightBody]:
                combineInp = combines.createInput(side, tools)
                combineInp.isKeepToolBodies = True
                combineInp.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
                combines.add(combineInp)

            tools = adsk.core.ObjectCollection.create()
            tools.add(frontBody)
            tools.add(backBody)
            tools.add(leftBody)
            tools.add(rightBody)
            for side in [baseBody, lidBody]:
                if side is None:
                    continue
                combineInp = combines.createInput(side, tools)
                combineInp.isKeepToolBodies = True
                combineInp.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
                combines.add(combineInp)

        except:
            if ui:
                ui.messageBox('Boxer failed:\n{}'.format(
                    traceback.format_exc()))


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


def calcFingers(edgeX: float, edgeY: float):
    """Calculate fingers for an edge. This routine will generate fingers about
    8* longer than the material thickness, and will always generate an odd 
    number of fingers (just because I think that looks better). The fingers will
    be centered on the edge being jointed. This routine will generate fingers
    along whichever of the two edges passed into it is longer - the shorter edge
    will be used as the material thickness."""
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
