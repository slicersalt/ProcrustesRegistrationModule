import os
import unittest
import vtk, qt, ctk, slicer
# from vtkFiltersHybridPython import vtkProcrustesAlignmentFilter
# from vtkFiltersKitPython import vtkMultiBlockDataGroupFilter
# from vtkCommonKitPython import vtkPointSet
# from vtkCommonKitPython import vtkMultiBlockDataSet
from slicer.ScriptedLoadableModule import *
import logging

#
# ProcrustesRegistrationModule
#

class ProcrustesRegistrationModule(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "Procrustes Registration"
    self.parent.categories = ["Shape Analysis"]
    self.parent.dependencies = []
    self.parent.contributors = ["Ye Han (Kitware, Inc.)"]
    self.parent.helpText = (
      "Procrustes registration using vtkProcrustesAlignmentFilter."
    )
    self.parent.helpText += self.getDefaultModuleDocumentationLink()
    self.parent.acknowledgementText = (
      "This file was originally developed by Jean-Christophe Fillion-Robin, "
      "Kitware Inc., Andras Lasso, PerkLab, and Steve Pieper, Isomics, Inc. "
      "and was partially funded by NIH grant 3P41RR013218-12S1."
    )

#
# ProcrustesRegistrationModuleWidget
#

class ProcrustesRegistrationModuleWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)

    # Instantiate and connect widgets ...

    #
    # Parameters Area
    #
    parametersCollapsibleButton = ctk.ctkCollapsibleButton()
    parametersCollapsibleButton.text = "Parameters"
    self.layout.addWidget(parametersCollapsibleButton)

    # Layout within the dummy collapsible button
    parametersFormLayout = qt.QFormLayout(parametersCollapsibleButton)

    #
    # input volume selector
    #
    self.inputSelector1 = slicer.qMRMLNodeComboBox()
    self.inputSelector1.nodeTypes = ["vtkMRMLModelNode"]
    self.inputSelector1.selectNodeUponCreation = False
    self.inputSelector1.addEnabled = False
    self.inputSelector1.removeEnabled = False
    self.inputSelector1.noneEnabled = False
    self.inputSelector1.showHidden = False
    self.inputSelector1.showChildNodeTypes = False
    self.inputSelector1.setMRMLScene( slicer.mrmlScene )
    self.inputSelector1.setToolTip( "Pick the input1 to the algorithm." )
    parametersFormLayout.addRow("Input Model1: ", self.inputSelector1)

    #
    # output volume selector
    #
    self.inputSelector2 = slicer.qMRMLNodeComboBox()
    self.inputSelector2.nodeTypes = ["vtkMRMLModelNode"]
    self.inputSelector2.selectNodeUponCreation = False
    self.inputSelector2.addEnabled = False
    self.inputSelector2.removeEnabled = False
    self.inputSelector2.noneEnabled = False
    self.inputSelector2.showHidden = False
    self.inputSelector2.showChildNodeTypes = False
    self.inputSelector2.setMRMLScene( slicer.mrmlScene )
    self.inputSelector2.setToolTip( "Pick the input2 to the algorithm." )
    parametersFormLayout.addRow("Input Model2: ", self.inputSelector2)

    #
    # output volume selector
    #
    self.inputSelector3 = slicer.qMRMLNodeComboBox()
    self.inputSelector3.nodeTypes = ["vtkMRMLModelNode"]
    self.inputSelector3.selectNodeUponCreation = True
    self.inputSelector3.addEnabled = False
    self.inputSelector3.removeEnabled = False
    self.inputSelector3.noneEnabled = False
    self.inputSelector3.showHidden = False
    self.inputSelector3.showChildNodeTypes = False
    self.inputSelector3.setMRMLScene( slicer.mrmlScene )
    self.inputSelector3.setToolTip( "Pick the input3 to the algorithm." )
    parametersFormLayout.addRow("Input Model3: ", self.inputSelector3)

    #
    # Apply Button
    #
    self.applyButton = qt.QPushButton("Apply")
    self.applyButton.toolTip = "Run the algorithm."
    self.applyButton.enabled = False
    parametersFormLayout.addRow(self.applyButton)

    # connections
    self.applyButton.connect('clicked(bool)', self.onApplyButton)
    self.inputSelector1.connect("currentNodeChanged(vtkMRMLNode*)", self.onSelect)
    self.inputSelector2.connect("currentNodeChanged(vtkMRMLNode*)", self.onSelect)
    self.inputSelector3.connect("currentNodeChanged(vtkMRMLNode*)", self.onSelect)

    # Add vertical spacer
    self.layout.addStretch(1)

    # Refresh Apply button state
    self.onSelect()

  def cleanup(self):
    pass

  def onSelect(self):
    self.applyButton.enabled = self.inputSelector1.currentNode() \
                               and self.inputSelector2.currentNode()\
                               and self.inputSelector3.currentNode()

  def onApplyButton(self):
    logic = ProcrustesRegistrationModuleLogic()
    logic.run(self.inputSelector1.currentNode(), self.inputSelector2.currentNode(), self.inputSelector3.currentNode())

#
# ProcrustesRegistrationModuleLogic
#

class ProcrustesRegistrationModuleLogic(ScriptedLoadableModuleLogic):

  def hasModelData(self,modelNode):
    """This is an example logic method that
    returns true if the passed in volume
    node has valid image data
    """
    if not modelNode:
      logging.debug('hasModelData failed: no volume node')
      return False
    if modelNode.GetMesh() is None:
      logging.debug('hasModelData failed: no poly data in model node')
      return False
    return True

  def run(self, inputModel1, inputModel2, inputModel3):
    """
    Run the actual algorithm
    """
    logging.info('Processing started')

    if not self.hasModelData(inputModel1):
      return False
    if not self.hasModelData(inputModel2):
      return False
    if not self.hasModelData(inputModel3):
      return False

    group = vtk.vtkMultiBlockDataGroupFilter()
    group.AddInputDataObject(inputModel1.GetMesh())
    group.AddInputDataObject(inputModel2.GetMesh())
    group.AddInputDataObject(inputModel3.GetMesh())
    group.Update()
    procrustes = vtk.vtkProcrustesAlignmentFilter()
    procrustes.SetInputConnection(group.GetOutputPort())
    procrustes.GetLandmarkTransform().SetModeToRigidBody()
    procrustes.Update()

    poly1 = procrustes.GetOutput().GetBlock(0)
    poly2 = procrustes.GetOutput().GetBlock(1)
    poly3 = procrustes.GetOutput().GetBlock(2)

    meanPoints = procrustes.GetMeanPoints()
    nPoints = meanPoints.GetNumberOfPoints()
    vertices = vtk.vtkCellArray()
    vertices.Allocate(nPoints)
    for ptId in range(nPoints):
      vertex = vtk.vtkVertex()
      vertex.GetPointIds().SetId(0, ptId)
      vertices.InsertNextCell(vertex)
    pointSets = vtk.vtkPolyData()
    pointSets.SetPoints(meanPoints)
    pointSets.SetVerts(vertices)

    scene = slicer.mrmlScene

    outputModel1 = slicer.vtkMRMLModelNode()
    outputModel1.SetScene(scene)
    outputModel1.SetName(scene.GenerateUniqueName(inputModel1.GetName() + "_aligned"))
    outputModel1.SetAndObservePolyData(poly1)

    modelDisplay1 = slicer.vtkMRMLModelDisplayNode()
    modelDisplay1.SetColor(0, 1, 1)  # cyan
    modelDisplay1.SetBackfaceCulling(0)
    modelDisplay1.SetScene(scene)
    scene.AddNode(modelDisplay1)
    outputModel1.SetAndObserveDisplayNodeID(modelDisplay1.GetID())
    scene.AddNode(outputModel1)

    outputModel2 = slicer.vtkMRMLModelNode()
    outputModel2.SetScene(scene)
    outputModel2.SetName(scene.GenerateUniqueName(inputModel2.GetName() + "_aligned"))
    outputModel2.SetAndObservePolyData(poly2)

    modelDisplay2 = slicer.vtkMRMLModelDisplayNode()
    modelDisplay2.SetColor(0, 1, 1)  # cyan
    modelDisplay2.SetBackfaceCulling(0)
    modelDisplay2.SetScene(scene)
    scene.AddNode(modelDisplay2)
    outputModel2.SetAndObserveDisplayNodeID(modelDisplay2.GetID())
    scene.AddNode(outputModel2)

    outputModel3 = slicer.vtkMRMLModelNode()
    outputModel3.SetScene(scene)
    outputModel3.SetName(scene.GenerateUniqueName(inputModel3.GetName() + "_aligned"))
    outputModel3.SetAndObservePolyData(poly3)

    modelDisplay3 = slicer.vtkMRMLModelDisplayNode()
    modelDisplay3.SetColor(0, 1, 1)  # cyan
    modelDisplay3.SetBackfaceCulling(0)
    modelDisplay3.SetScene(scene)
    scene.AddNode(modelDisplay3)
    outputModel3.SetAndObserveDisplayNodeID(modelDisplay3.GetID())
    scene.AddNode(outputModel3)

    meanPointModel = slicer.vtkMRMLModelNode()
    meanPointModel.SetScene(scene)
    meanPointModel.SetName(scene.GenerateUniqueName("mean_points"))
    meanPointModel.SetAndObservePolyData(pointSets)

    meanPointDisplay = slicer.vtkMRMLModelDisplayNode()
    meanPointDisplay.SetColor(1, 0, 0)  # cyan
    meanPointDisplay.SetBackfaceCulling(0)
    meanPointDisplay.SetScene(scene)
    scene.AddNode(meanPointDisplay)
    meanPointModel.SetAndObserveDisplayNodeID(meanPointDisplay.GetID())
    scene.AddNode(meanPointModel)

    logging.info('Processing completed')

    return True


class ProcrustesRegistrationModuleTest(ScriptedLoadableModuleTest):
  """
  This is the test case for your scripted module.
  Uses ScriptedLoadableModuleTest base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setUp(self):
    """ Do whatever is needed to reset the state - typically a scene clear will be enough.
    """
    slicer.mrmlScene.Clear(0)

  def runTest(self):
    """Run as few or as many tests as needed here.
    """
    self.setUp()
    self.test_ProcrustesRegistrationModule1()

  def test_ProcrustesRegistrationModule1(self):
    """ Ideally you should have several levels of tests.  At the lowest level
    tests should exercise the functionality of the logic with different inputs
    (both valid and invalid).  At higher levels your tests should emulate the
    way the user would interact with your code and confirm that it still works
    the way you intended.
    One of the most important features of the tests is that it should alert other
    developers when their changes will have an impact on the behavior of your
    module.  For example, if a developer removes a feature that you depend on,
    your test should break so they know that the feature is needed.

    self.delayDisplay("Starting the test")
    #
    # first, get some data
    #
    import SampleData
    SampleData.downloadFromURL(
      nodeNames='FA',
      fileNames='FA.nrrd',
      uris='http://slicer.kitware.com/midas3/download?items=5767')
    self.delayDisplay('Finished with download and loading')

    volumeNode = slicer.util.getNode(pattern="FA")
    logic = ProcrustesRegistrationModuleLogic()
    self.assertIsNotNone( logic.hasImageData(volumeNode) )
    self.delayDisplay('Test passed!')
    """

