#!/usr/bin/env python
import binascii

from absl import app
from selenium.webdriver.common import keys

from grr_response_core.lib.rdfvalues import client_fs as rdf_client_fs
from grr_response_core.lib.rdfvalues import crypto as rdf_crypto
from grr_response_core.lib.rdfvalues import file_finder as rdf_file_finder
from grr_response_core.lib.rdfvalues import paths as rdf_paths
from grr_response_proto import flows_pb2
from grr_response_proto import jobs_pb2
from grr_response_proto.api import flow_pb2
from grr_response_server.flows import file
from grr_response_server.flows.general import transfer
from grr_response_server.gui import api_call_context
from grr_response_server.gui import gui_test_lib
from grr_response_server.gui.api_plugins import flow as api_flow
from grr.test_lib import fixture_test_lib
from grr.test_lib import flow_test_lib
from grr.test_lib import test_lib


class CollectFilesByKnownPathTest(gui_test_lib.GRRSeleniumTest):
  """Tests the CollectFilesByKnownPath Flow."""

  def _GenCollectedResult(
      self, i: int
  ) -> rdf_file_finder.CollectFilesByKnownPathResult:
    return rdf_file_finder.CollectFilesByKnownPathResult(
        stat=rdf_client_fs.StatEntry(
            pathspec=rdf_paths.PathSpec.OS(path=f"/file{i}"),
            st_size=i,
        ),
        hash=rdf_crypto.Hash(
            sha256=binascii.unhexlify(
                "9e8dc93e150021bb4752029ebbff51394aa36f069cf19901578e4f06017acdb5"
            ),
            sha1=binascii.unhexlify("6dd6bee591dfcb6d75eb705405302c3eab65e21a"),
            md5=binascii.unhexlify("8b0a15eefe63fd41f8dc9dee01c5cf9a"),
        ),
        status=rdf_file_finder.CollectFilesByKnownPathResult.Status.COLLECTED,
    )

  def _GenFailedResult(
      self, i: int
  ) -> rdf_file_finder.CollectFilesByKnownPathResult:
    return rdf_file_finder.CollectFilesByKnownPathResult(
        stat=rdf_client_fs.StatEntry(
            pathspec=rdf_paths.PathSpec.OS(path=f"/file{i}"),
        ),
        status=rdf_file_finder.CollectFilesByKnownPathResult.Status.FAILED,
        error=f"errormsg{i}",
    )

  def setUp(self):
    super().setUp()
    self.client_id = self.SetupClient(0)
    self.RequestAndGrantClientApproval(self.client_id)

  def testDisplaysOnlyWhenCollected(self):
    flow_args = rdf_file_finder.CollectFilesByKnownPathArgs(paths=["/file0"])
    flow_test_lib.StartFlow(
        file.CollectFilesByKnownPath,
        creator=self.test_username,
        client_id=self.client_id,
        flow_args=flow_args,
    )

    with flow_test_lib.FlowProgressOverride(
        file.CollectFilesByKnownPath,
        rdf_file_finder.CollectFilesByKnownPathProgress(num_in_progress=1),
    ):
      self.Open(f"/v2/clients/{self.client_id}")
      self.WaitUntil(
          self.IsElementPresent,
          "css=.flow-title:contains('Collect files from exact paths')",
      )
      self.WaitUntil(
          self.IsElementPresent,
          "css=collect-files-by-known-path-details"
          " result-accordion:contains('/file0')",
      )
      self.Click(
          "css=collect-files-by-known-path-details"
          " result-accordion:contains('/file0')"
      )
      self.WaitUntil(
          self.IsElementPresent,
          "css=collect-files-by-known-path-details .results:contains('No"
          " data')",
      )

  def testDisplaysCollectedResult(self):
    flow_args = rdf_file_finder.CollectFilesByKnownPathArgs(
        paths=["/file0", "/file1", "/file2"]
    )
    flow_id = flow_test_lib.StartFlow(
        file.CollectFilesByKnownPath,
        creator=self.test_username,
        client_id=self.client_id,
        flow_args=flow_args,
    )

    flow_test_lib.AddResultsToFlow(
        self.client_id, flow_id, [self._GenCollectedResult(i) for i in range(3)]
    )

    with flow_test_lib.FlowProgressOverride(
        file.CollectFilesByKnownPath,
        rdf_file_finder.CollectFilesByKnownPathProgress(num_collected=3),
    ):
      self.Open(f"/v2/clients/{self.client_id}")
      self.Click(
          "css=collect-files-by-known-path-details"
          " result-accordion:contains('/file0 + 2 more')"
      )

      self.WaitUntil(
          self.IsElementPresent,
          "css=collect-files-by-known-path-details"
          " [role=tab]:contains('3 successful file collections')",
      )
      for i in range(3):
        self.WaitUntil(
            self.IsElementPresent,
            "css=collect-files-by-known-path-details"
            f" .results:contains('{i} B')",
        )

  def testDisplaysFailedResult(self):
    flow_args = rdf_file_finder.CollectFilesByKnownPathArgs(
        paths=["/file0", "/file1"]
    )
    flow_id = flow_test_lib.StartFlow(
        file.CollectFilesByKnownPath,
        creator=self.test_username,
        client_id=self.client_id,
        flow_args=flow_args,
    )

    flow_test_lib.AddResultsToFlow(
        self.client_id, flow_id, [self._GenFailedResult(i) for i in range(2)]
    )

    with flow_test_lib.FlowProgressOverride(
        file.CollectFilesByKnownPath,
        rdf_file_finder.CollectFilesByKnownPathProgress(num_failed=2),
    ):
      self.Open(f"/v2/clients/{self.client_id}")
      self.Click(
          "css=collect-files-by-known-path-details"
          " result-accordion:contains('/file0 + 1 more')"
      )

      self.WaitUntil(
          self.IsElementPresent,
          "css=collect-files-by-known-path-details"
          " [role=tab]:contains('2 errors')",
      )
      for i in range(2):
        self.WaitUntil(
            self.IsElementPresent,
            "css=collect-files-by-known-path-details"
            f" .results:contains('errormsg{i}')",
        )

  def testDisplaysSuccessAndFailedResultAndWarning(self):
    flow_args = rdf_file_finder.CollectFilesByKnownPathArgs(
        paths=["/file0", "/file1"]
    )
    flow_id = flow_test_lib.StartFlow(
        file.CollectFilesByKnownPath,
        creator=self.test_username,
        client_id=self.client_id,
        flow_args=flow_args,
    )

    flow_test_lib.AddResultsToFlow(
        self.client_id,
        flow_id,
        [
            self._GenFailedResult(0),
            self._GenCollectedResult(1),
        ],
    )

    with flow_test_lib.FlowProgressOverride(
        file.CollectFilesByKnownPath,
        rdf_file_finder.CollectFilesByKnownPathProgress(
            num_collected=1, num_raw_fs_access_retries=1, num_failed=1
        ),
    ):
      self.Open(f"/v2/clients/{self.client_id}")
      self.Click(
          "css=collect-files-by-known-path-details"
          " result-accordion:contains('/file0 + 1 more')"
      )

      self.WaitUntil(
          self.IsElementPresent,
          "css=collect-files-by-known-path-details .results:contains('1 file"
          " fetched by parsing the raw disk image with libtsk or libfsntfs.')",
      )

      self.WaitUntil(
          self.IsElementPresent,
          "css=collect-files-by-known-path-details"
          " [role=tab]:contains('1 successful file collection')",
      )
      self.WaitUntil(
          self.IsElementPresent,
          "css=collect-files-by-known-path-details .results:contains('1 B')",
      )

      self.WaitUntil(
          self.IsElementPresent,
          "css=collect-files-by-known-path-details"
          " [role=tab]:contains('1 error')",
      )
      self.Click(
          "css=collect-files-by-known-path-details"
          " [role=tab]:contains('1 error')"
      )
      self.WaitUntil(
          self.IsElementPresent,
          "css=collect-files-by-known-path-details"
          " .results:contains('errormsg0')",
      )

  def testDownloadButtonFlowFinished(self):
    flow_args = rdf_file_finder.CollectFilesByKnownPathArgs(paths=["/file0"])
    flow_id = flow_test_lib.StartFlow(
        file.CollectFilesByKnownPath,
        creator=self.test_username,
        client_id=self.client_id,
        flow_args=flow_args,
    )
    flow_test_lib.OverrideFlowResultMetadataInFlow(
        self.client_id,
        flow_id,
        flows_pb2.FlowResultMetadata(
            is_metadata_set=True,
            num_results_per_type_tag=[
                flows_pb2.FlowResultCount(
                    type=flows_pb2.CollectFilesByKnownPathResult.__name__,
                    count=1,
                )
            ],
        ),
    )
    flow_test_lib.MarkFlowAsFinished(self.client_id, flow_id)

    self.Open(f"/v2/clients/{self.client_id}")
    self.WaitUntil(
        self.IsElementPresent,
        "css=a[mat-stroked-button]:contains('Download')",
    )

  def testFlowError(self):
    flow_args = rdf_file_finder.CollectFilesByKnownPathArgs(
        paths=["/file0", "/file1"]
    )
    flow_id = flow_test_lib.StartFlow(
        file.CollectFilesByKnownPath,
        creator=self.test_username,
        client_id=self.client_id,
        flow_args=flow_args,
    )

    flow_test_lib.MarkFlowAsFailed(self.client_id, flow_id)

    self.Open(f"/v2/clients/{self.client_id}")
    self.WaitUntil(self.IsElementPresent, "css=flow-details mat-icon.error")

  def testDisplaysArgumentsPopup(self):
    flow_args = rdf_file_finder.CollectFilesByKnownPathArgs(
        paths=["/file0", "/file1"]
    )
    flow_test_lib.StartFlow(
        file.CollectFilesByKnownPath,
        creator=self.test_username,
        client_id=self.client_id,
        flow_args=flow_args,
    )

    self.Open(f"/v2/clients/{self.client_id}")
    self.WaitUntil(
        self.IsElementPresent,
        "css=.flow-title:contains('Collect files from exact paths')",
    )

    self.Click("css=result-accordion .title:contains('Flow arguments')")

    self.WaitUntil(self.IsElementPresent, "css=textarea[name=paths]")
    path_input = self.GetElement("css=textarea[name=paths]")
    self.assertEqual("/file0\n/file1", path_input.get_attribute("value"))

  def testFlowArgumentForm(self):
    self.Open(f"/v2/clients/{self.client_id}")

    self.Click('css=flow-form button:contains("Collect files")')
    self.Click(
        'css=.mat-mdc-menu-panel button:contains("Collect files from exact'
        ' paths")'
    )

    element = self.WaitUntil(
        self.GetVisibleElement, "css=flow-args-form textarea[name=paths]"
    )
    element.send_keys("/foo/firstpath")
    element.send_keys(keys.Keys.ENTER)
    element.send_keys("/bar/secondpath")

    self.Click('css=flow-form button:contains("Start")')

    def FlowHasBeenStarted():
      handler = api_flow.ApiListFlowsHandler()
      flows = handler.Handle(
          flow_pb2.ApiListFlowsArgs(
              client_id=self.client_id, top_flows_only=True
          ),
          context=api_call_context.ApiCallContext(username=self.test_username),
      ).items
      return flows[0] if len(flows) == 1 else None

    flow = self.WaitUntil(FlowHasBeenStarted)

    self.assertEqual(flow.name, file.CollectFilesByKnownPath.__name__)
    flow_args = flows_pb2.CollectFilesByKnownPathArgs()
    flow.args.Unpack(flow_args)
    self.assertCountEqual(
        flow_args.paths, ["/foo/firstpath", "/bar/secondpath"]
    )


class VfsFileViewTest(gui_test_lib.GRRSeleniumTest):

  def setUp(self):
    super().setUp()
    self.client_id = "C.0000000000000001"

    with test_lib.FakeTime(test_lib.FIXED_TIME):
      fixture_test_lib.ClientFixture(self.client_id)

    gui_test_lib.CreateFileVersions(self.client_id)
    self.RequestAndGrantClientApproval("C.0000000000000001")

  def testShowsVfsFileContentsInDrawer(self):
    gui_test_lib.CreateFileVersion(
        self.client_id,
        "fs/os/foo/barfile",
        "Hello VFS View".encode("utf-8"),
        timestamp=gui_test_lib.TIME_1,
    )

    self.Open(
        f"/v2/clients/{self.client_id}(drawer:files/os/%2Ffoo%2Fbarfile/text)"
    )

    self.WaitUntilContains("barfile", self.GetText, "css=mat-drawer")
    self.WaitUntilContains("Hello VFS View", self.GetText, "css=mat-drawer")

  def testShowsVfsFileStatInDrawer(self):
    gui_test_lib.CreateFileVersion(
        self.client_id,
        "fs/os/foo/barfile",
        "Hello VFS View".encode("utf-8"),
        timestamp=gui_test_lib.TIME_1,
    )

    self.Open(
        f"/v2/clients/{self.client_id}(drawer:files/os/%2Ffoo%2Fbarfile/stat)"
    )

    self.WaitUntilContains("barfile", self.GetText, "css=mat-drawer")
    self.assertContainsInOrder(
        [
            "SHA-256",
            "23406c404b29af3a449196db4833de182b9b955df14cef54fb6004189968c154",
        ],
        self.GetText("css=mat-drawer"),
    )

  def testNavigateToFileInFilesView(self):
    gui_test_lib.CreateFileVersion(
        self.client_id,
        "fs/os/foofolder/subfolder/barfile",
        "Hello VFS View".encode("utf-8"),
        timestamp=gui_test_lib.TIME_1,
    )

    self.Open(f"/v2/clients/{self.client_id}")

    self.Click("css=a.collected-files-tab")

    self.WaitUntilContains("files", self.GetCurrentUrlPath)

    self.Click("css=mat-tree a:contains('foofolder')")

    self.Click("css=mat-tree a:contains('subfolder')")

    self.Click("css=table.directory-table td:contains('barfile')")

    self.WaitUntilContains("barfile", self.GetCurrentUrlPath)

    self.WaitUntilContains("st_size 14 B", self.GetText, "css=app-stat-view")

    self.Click("css=a[role=tab]:contains('Text content')")

    self.WaitUntilContains("text", self.GetCurrentUrlPath)

    self.WaitUntilContains(
        "Hello VFS View", self.GetText, "css=app-file-details"
    )

  def testTriggersMultiGetFilesFlow(self):
    gui_test_lib.CreateFileVersion(
        self.client_id,
        "fs/os/foo/barfile",
        "Hello VFS View".encode("utf-8"),
        timestamp=gui_test_lib.TIME_1,
    )

    self.Open(f"/v2/clients/{self.client_id}(drawer:files/os/%2Ffoo%2Fbarfile)")

    self.WaitUntilContains("/foo/barfile", self.GetText, "css=mat-drawer")

    self.Click("css=button.recollect")
    self.Click("css=.mat-drawer-backdrop")
    self.WaitUntilNot(self.IsElementPresent, "css=mat-drawer")

    self.WaitUntil(
        self.IsElementPresent,
        "css=flow-details:contains('MultiGetFile')"
        " .title:contains('/foo/barfile')",
    )


class MultiGetFileTest(gui_test_lib.GRRSeleniumTest):
  """Tests the MultiGetFile Flow."""

  def _GenSampleResult(self, i: int) -> rdf_client_fs.StatEntry:
    return rdf_client_fs.StatEntry(
        pathspec=rdf_paths.PathSpec.OS(path=f"/somefile{i}"),
        st_mode=33184,
        st_size=4242,
        st_atime=1336469177,
        st_mtime=1336129892,
        st_ctime=1336129892,
    )

  def setUp(self):
    super().setUp()
    self.client_id = self.SetupClient(0)
    self.RequestAndGrantClientApproval(self.client_id)

  def testCorrectlyDisplaysMultiGetFileResults(self):
    flow_args = transfer.MultiGetFileArgs(
        pathspecs=[
            rdf_paths.PathSpec.OS(path=f"/somefile{i}") for i in range(10)
        ]
    )
    flow_id = flow_test_lib.StartFlow(
        transfer.MultiGetFile,
        creator=self.test_username,
        client_id=self.client_id,
        flow_args=flow_args,
    )

    with flow_test_lib.FlowProgressOverride(
        transfer.MultiGetFile,
        transfer.MultiGetFileProgress(
            num_pending_hashes=0,
            num_pending_files=2,
            num_skipped=0,
            num_collected=3,
            num_failed=5,
        ),
    ):
      self.Open(f"/v2/clients/{self.client_id}")
      self.WaitUntil(
          self.IsElementPresent, "css=.flow-title:contains('MultiGetFile')"
      )

      flow_test_lib.AddResultsToFlow(
          self.client_id, flow_id, [self._GenSampleResult(i) for i in range(3)]
      )

      self.Click(
          "css=multi-get-file-flow-details result-accordion"
          " .title:contains('/somefile0 + 9 more')"
      )
      for i in range(3):
        self.WaitUntil(
            self.IsElementPresent,
            f"css=multi-get-file-flow-details td:contains('/somefile{i}')",
        )


class StatMultipleFilesTest(gui_test_lib.GRRSeleniumTest):
  """Tests the StatMultipleFiles Flow."""

  def _GenCollectedResult(self, i: int) -> rdf_client_fs.StatEntry:
    return rdf_client_fs.StatEntry(
        pathspec=rdf_paths.PathSpec.OS(path=f"/file{i}"),
        st_size=i,
    )

  def setUp(self):
    super().setUp()
    self.client_id = self.SetupClient(0)
    self.RequestAndGrantClientApproval(self.client_id)

  def testDisplaysOnlyWhenResultsCollected(self):
    flow_args = rdf_file_finder.StatMultipleFilesArgs(
        path_expressions=["/file0"]
    )
    flow_test_lib.StartFlow(
        file.StatMultipleFiles,
        creator=self.test_username,
        client_id=self.client_id,
        flow_args=flow_args,
    )

    self.Open(f"/v2/clients/{self.client_id}")

    self.WaitUntil(
        self.IsElementPresent, "css=.flow-title:contains('Stat files')"
    )

    self.assertFalse(
        self.IsElementPresent("css=result-accordion file-results-table"),
    )

  def testDisplaysCollectedResult(self):
    flow_args = rdf_file_finder.StatMultipleFilesArgs(
        path_expressions=["/file0", "/file1", "/file2"]
    )
    flow_id = flow_test_lib.StartFlow(
        file.StatMultipleFiles,
        creator=self.test_username,
        client_id=self.client_id,
        flow_args=flow_args,
    )
    flow_test_lib.OverrideFlowResultMetadataInFlow(
        self.client_id,
        flow_id,
        flows_pb2.FlowResultMetadata(
            is_metadata_set=True,
            num_results_per_type_tag=[
                flows_pb2.FlowResultCount(
                    type=jobs_pb2.StatEntry.__name__, count=3
                )
            ],
        ),
    )
    flow_test_lib.AddResultsToFlow(
        self.client_id, flow_id, [self._GenCollectedResult(i) for i in range(3)]
    )

    self.Open(f"/v2/clients/{self.client_id}")
    self.WaitUntil(
        self.IsElementPresent,
        "css=result-accordion:contains('/file0 + 2 more')",
    )

    self.Click("css=result-accordion:contains('/file0 + 2 more')")

    for i in range(3):
      self.WaitUntil(
          self.IsElementPresent,
          f"css=file-results-table:contains('{i} B')",
      )

  def testDownloadButtonFlowFinished(self):
    flow_args = rdf_file_finder.StatMultipleFilesArgs(
        path_expressions=["/file0"]
    )
    flow_id = flow_test_lib.StartFlow(
        file.StatMultipleFiles,
        creator=self.test_username,
        client_id=self.client_id,
        flow_args=flow_args,
    )
    flow_test_lib.OverrideFlowResultMetadataInFlow(
        self.client_id,
        flow_id,
        flows_pb2.FlowResultMetadata(
            is_metadata_set=True,
            num_results_per_type_tag=[
                flows_pb2.FlowResultCount(
                    type=jobs_pb2.StatEntry.__name__, count=1
                )
            ],
        ),
    )
    flow_test_lib.MarkFlowAsFinished(self.client_id, flow_id)

    self.Open(f"/v2/clients/{self.client_id}")
    self.WaitUntil(
        self.IsElementPresent,
        "css=a[mat-stroked-button]:contains('Download')",
    )

  def testFlowError(self):
    flow_args = rdf_file_finder.StatMultipleFilesArgs(
        path_expressions=["/file0", "/file1"]
    )
    flow_id = flow_test_lib.StartFlow(
        file.StatMultipleFiles,
        creator=self.test_username,
        client_id=self.client_id,
        flow_args=flow_args,
    )

    flow_test_lib.MarkFlowAsFailed(self.client_id, flow_id)

    self.Open(f"/v2/clients/{self.client_id}")
    self.WaitUntil(self.IsElementPresent, "css=flow-details mat-icon.error")

  def testDisplaysArgumentsAccordion(self):
    flow_args = rdf_file_finder.StatMultipleFilesArgs(
        path_expressions=["/file0", "/file1"]
    )
    flow_test_lib.StartFlow(
        file.StatMultipleFiles,
        creator=self.test_username,
        client_id=self.client_id,
        flow_args=flow_args,
    )

    self.Open(f"/v2/clients/{self.client_id}")
    self.WaitUntil(
        self.IsElementPresent,
        "css=.flow-title:contains('Stat files')",
    )

    self.Click("css=result-accordion .title:contains('Flow arguments')")

    self.WaitUntil(
        self.IsElementPresent,
        "css=app-glob-expression-input",
    )
    path_input = self.GetElement(
        "css=app-glob-expression-input[id=path0] input"
    )
    self.assertEqual("/file0", path_input.get_attribute("value"))

    path_input_2 = self.GetElement(
        "css=app-glob-expression-input[id=path1] input"
    )
    self.assertEqual("/file1", path_input_2.get_attribute("value"))

  def testFlowArgumentForm(self):
    self.Open(f"/v2/clients/{self.client_id}")

    self.WaitUntil(self.IsElementPresent, "css=app-flow-picker")
    self.Type('css=app-flow-picker input[name="flowSearchBox"]', "stat")
    self.Click('css=[role=option]:Contains("Stat files")')

    element = self.WaitUntil(
        self.GetVisibleElement,
        "css=flow-args-form app-glob-expression-input[id=path0] input",
    )
    element.send_keys("/foo/firstpath")

    self.Click('css=flow-form button:contains("Add path expression")')

    element = self.WaitUntil(
        self.GetVisibleElement,
        "css=flow-args-form app-glob-expression-input[id=path1] input",
    )
    element.send_keys("/bar/secondpath")

    self.Click('css=flow-form button:contains("Start")')

    def FlowHasBeenStarted():
      handler = api_flow.ApiListFlowsHandler()
      flows = handler.Handle(
          flow_pb2.ApiListFlowsArgs(
              client_id=self.client_id, top_flows_only=True
          ),
          context=api_call_context.ApiCallContext(username=self.test_username),
      ).items
      return flows[0] if len(flows) == 1 else None

    flow = self.WaitUntil(FlowHasBeenStarted)

    self.assertEqual(flow.name, file.StatMultipleFiles.__name__)
    flow_args = flows_pb2.StatMultipleFilesArgs()
    flow.args.Unpack(flow_args)
    self.assertCountEqual(
        flow_args.path_expressions, ["/foo/firstpath", "/bar/secondpath"]
    )


class HashMultipleFilesTest(gui_test_lib.GRRSeleniumTest):
  """Tests the HashMultipleFiles Flow."""

  def _GenCollectedResult(
      self, i: int
  ) -> rdf_file_finder.CollectMultipleFilesResult:
    return rdf_file_finder.CollectMultipleFilesResult(
        stat=rdf_client_fs.StatEntry(
            pathspec=rdf_paths.PathSpec.OS(path=f"/file{i}"),
            st_size=i,
        ),
        hash=rdf_crypto.Hash(
            sha256=binascii.unhexlify(
                "9e8dc93e150021bb4752029ebbff51394aa36f069cf19901578e4f06017acdb5"
            ),
            sha1=binascii.unhexlify("6dd6bee591dfcb6d75eb705405302c3eab65e21a"),
            md5=binascii.unhexlify("8b0a15eefe63fd41f8dc9dee01c5cf9a"),
        ),
        status=rdf_file_finder.CollectMultipleFilesResult.Status.COLLECTED,
    )

  def _GenFailedResult(
      self,
      i: int,
  ) -> rdf_file_finder.CollectMultipleFilesResult:
    return rdf_file_finder.CollectMultipleFilesResult(
        stat=rdf_client_fs.StatEntry(
            pathspec=rdf_paths.PathSpec.OS(path=f"/file{i}"),
        ),
        status=rdf_file_finder.CollectMultipleFilesResult.Status.FAILED,
        error=f"errormsg{i}",
    )

  def setUp(self):
    super().setUp()
    self.client_id = self.SetupClient(0)
    self.RequestAndGrantClientApproval(self.client_id)

  def testDisplaysOnlyWhenCollected(self):
    flow_args = rdf_file_finder.HashMultipleFilesArgs(
        path_expressions=["/file0"]
    )
    flow_test_lib.StartFlow(
        file.HashMultipleFiles,
        creator=self.test_username,
        client_id=self.client_id,
        flow_args=flow_args,
    )

    with flow_test_lib.FlowProgressOverride(
        file.HashMultipleFiles,
        rdf_file_finder.HashMultipleFilesProgress(num_in_progress=1),
    ):
      self.Open(f"/v2/clients/{self.client_id}")

      self.WaitUntil(
          self.IsElementPresent,
          "css=.flow-title:contains('Hash files')",
      )

    self.assertFalse(
        self.IsElementPresent("css=result-accordion file-results-table"),
    )

  def testDisplaysCollectedResult(self):
    flow_args = rdf_file_finder.HashMultipleFilesArgs(
        path_expressions=["/file0", "/file1", "/file2"]
    )
    flow_id = flow_test_lib.StartFlow(
        file.HashMultipleFiles,
        creator=self.test_username,
        client_id=self.client_id,
        flow_args=flow_args,
    )

    flow_test_lib.AddResultsToFlow(
        self.client_id, flow_id, [self._GenCollectedResult(i) for i in range(3)]
    )

    with flow_test_lib.FlowProgressOverride(
        file.HashMultipleFiles,
        rdf_file_finder.HashMultipleFilesProgress(num_hashed=3),
    ):
      self.Open(f"/v2/clients/{self.client_id}")
      self.WaitUntil(
          self.IsElementPresent,
          "css=.flow-title:contains('Hash files')",
      )

      self.Click("css=result-accordion:contains('/file0 + 2 more')")

      for i in range(3):
        self.WaitUntil(
            self.IsElementPresent,
            f"css=result-accordion .results:contains('{i} B')",
        )

  def testDownloadButtonFlowFinished(self):
    flow_args = rdf_file_finder.HashMultipleFilesArgs(
        path_expressions=["/file0"]
    )
    flow_id = flow_test_lib.StartFlow(
        file.HashMultipleFiles,
        creator=self.test_username,
        client_id=self.client_id,
        flow_args=flow_args,
    )
    flow_test_lib.OverrideFlowResultMetadataInFlow(
        self.client_id,
        flow_id,
        flows_pb2.FlowResultMetadata(
            is_metadata_set=True,
            num_results_per_type_tag=[
                flows_pb2.FlowResultCount(
                    type=flows_pb2.CollectMultipleFilesResult.__name__, count=1
                )
            ],
        ),
    )
    flow_test_lib.MarkFlowAsFinished(self.client_id, flow_id)

    self.Open(f"/v2/clients/{self.client_id}")
    self.WaitUntil(
        self.IsElementPresent,
        "css=a[mat-stroked-button]:contains('Download')",
    )

  def testFlowError(self):
    flow_args = rdf_file_finder.HashMultipleFilesArgs(
        path_expressions=["/file0", "/file1"]
    )
    flow_id = flow_test_lib.StartFlow(
        file.HashMultipleFiles,
        creator=self.test_username,
        client_id=self.client_id,
        flow_args=flow_args,
    )

    flow_test_lib.MarkFlowAsFailed(self.client_id, flow_id)

    self.Open(f"/v2/clients/{self.client_id}")
    self.WaitUntil(self.IsElementPresent, "css=flow-details mat-icon.error")

  def testDisplaysArgumentsAccordion(self):
    flow_args = rdf_file_finder.HashMultipleFilesArgs(
        path_expressions=["/file0", "/file1"]
    )
    flow_test_lib.StartFlow(
        file.HashMultipleFiles,
        creator=self.test_username,
        client_id=self.client_id,
        flow_args=flow_args,
    )

    self.Open(f"/v2/clients/{self.client_id}")
    self.WaitUntil(
        self.IsElementPresent,
        "css=.flow-title:contains('Hash files')",
    )

    self.Click("css=result-accordion .title:contains('Flow arguments')")

    self.WaitUntil(
        self.IsElementPresent,
        "css=app-glob-expression-input",
    )
    path_input = self.GetElement(
        "css=app-glob-expression-input[id=path0] input"
    )
    self.assertEqual("/file0", path_input.get_attribute("value"))

    path_input_2 = self.GetElement(
        "css=app-glob-expression-input[id=path1] input"
    )
    self.assertEqual("/file1", path_input_2.get_attribute("value"))

  def testFlowArgumentForm(self):
    self.Open(f"/v2/clients/{self.client_id}")

    self.WaitUntil(self.IsElementPresent, "css=app-flow-picker")
    self.Type('css=app-flow-picker input[name="flowSearchBox"]', "hash")
    self.Click('css=[role=option]:Contains("Hash files")')

    element = self.WaitUntil(
        self.GetVisibleElement,
        "css=flow-args-form app-glob-expression-input[id=path0] input",
    )
    element.send_keys("/foo/firstpath")

    self.Click('css=flow-form button:contains("Add path expression")')

    element = self.WaitUntil(
        self.GetVisibleElement,
        "css=flow-args-form app-glob-expression-input[id=path1] input",
    )
    element.send_keys("/bar/secondpath")

    self.Click('css=flow-form button:contains("Start")')

    def FlowHasBeenStarted():
      handler = api_flow.ApiListFlowsHandler()
      flows = handler.Handle(
          flow_pb2.ApiListFlowsArgs(
              client_id=self.client_id, top_flows_only=True
          ),
          context=api_call_context.ApiCallContext(username=self.test_username),
      ).items
      return flows[0] if len(flows) == 1 else None

    flow = self.WaitUntil(FlowHasBeenStarted)

    self.assertEqual(flow.name, file.HashMultipleFiles.__name__)
    flow_args = flows_pb2.HashMultipleFilesArgs()
    flow.args.Unpack(flow_args)
    self.assertCountEqual(
        flow_args.path_expressions, ["/foo/firstpath", "/bar/secondpath"]
    )


if __name__ == "__main__":
  app.run(test_lib.main)
