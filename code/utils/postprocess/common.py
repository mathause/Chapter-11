import time
import traceback  # noqa: F401

from ..file_utils import _any_file_does_not_exist
from .weights_masks import MasksMixin, WeightsMixin


class Processor(MasksMixin, WeightsMixin):
    """(post-) process CMIP data"""

    def __init__(self, conf_cmip):
        """process CMIP5 or CMIP6 data"""

        self.conf_cmip = conf_cmip

        self._postprocess_name = None
        self._all_files = None

        self._files_kwargs = None

    @property
    def postprocess_name(self):
        """name of this postprocessing step"""

        if self._postprocess_name is None:
            raise AttributeError("postprocess_name is not set!")
        return self._postprocess_name

    @postprocess_name.setter
    def postprocess_name(self, value):
        self._postprocess_name = value

    @property
    def all_files(self):
        """all files to postprocess, initialize with find_all_files"""

        return self._all_files

    @all_files.setter
    def all_files(self, value):

        if self._all_files is not None:
            raise AttributeError("files already set!")

        print(f"Found {len(value)} simulations")
        self._all_files = value

    def find_all_files(self):
        """find all files that should be processed"""
        raise NotImplementedError("Implement in subclass.")

    def set_files_kwargs(self, **kwargs):
        """set the metadata to determine which files should be processed"""
        self._files_kwargs = kwargs

    def find_new_simulations(self):
        """determine unprocessed simulations in ``all_files``"""

        files = self.all_files

        files_to_process = list()
        for file, meta in files:

            fN_out = self.fN_out(**meta)

            if _any_file_does_not_exist(fN_out):
                files_to_process.append([file, meta])

        print(f"{len(files_to_process)} unprocessed simulations", end="\n\n")
        self.files_to_process = files_to_process

    def fN_out(self, **meta):
        """create output file name"""

        # make sure postprocess does not get deleted
        meta = meta.copy()

        # remove postprocess from meta - is given by self.postprocess_name
        meta.pop("postprocess", None)

        return self.conf_cmip.files_post.create_full_name(
            postprocess=self.postprocess_name, **meta
        )

    def _yield_filenames(self, **kwargs):

        print("")
        print(f"Processing {str(self)}")
        print(f"- files_kwargs: {self._files_kwargs}")
        print("")

        self.find_all_files()
        self.find_new_simulations()

        self.transform_kwargs = kwargs
        n_to_process = len(self.files_to_process)

        if self.files_to_process:
            self.conf_cmip._create_folder_for_output(
                self.files_to_process, self.postprocess_name
            )

        for i, (file, meta) in enumerate(self.files_to_process):
            now = time.strftime("%Y.%m.%d %H:%M:%S", time.localtime())
            fN_out = self.fN_out(**meta)
            print(f"processing {i + 1} of {n_to_process} ({now})")
            print(f"- {meta}")
            print(f"- {file}")
            print(f"- {fN_out}")

            yield file, meta

    def transform(self, **kwargs):

        for file, meta in self._yield_filenames(**kwargs):

            try:
                ds = self._transform(**meta)
                fN_out = self.fN_out(**meta)
                self.save(ds, fN_out)
            except Exception as err:
                raise err
                # traceback.print_tb(err.__traceback__)

    def _transform(self, **meta):
        """transform single simulation, TBD by subclass"""
        raise NotImplementedError("Implement in subclass.")

    def save(self, ds, fN_out):
        """save created dataset

        Parameters
        ----------
        ds : xr.Dataset
            The dataset created from transform.
        fN_out : str
            The file name to save the dataset. Created from ``fN_out(**meta)``.
        """

        # folder is created in _yield_filenames

        if ds is None:
            raise ValueError("Forgot to return ds?")

        if len(ds) != 0:
            ds.to_netcdf(fN_out, format="NETCDF4_CLASSIC")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def __repr__(self):
        """provide a nice str repr of the Processor"""

        klass = self.__class__.__name__
        ppn = "" if self._postprocess_name is None else f" ({self._postprocess_name})"
        cmip = self.conf_cmip.cmip_version.upper()

        return f"{cmip}: <{klass}>{ppn}"


# TODO: unify ProcessorFromOrig & ProcessorFromPost to avoid having two code paths
# use bridge/ strategy pattern instead of subclassing
# The start should be easy - pass the correct function to use in `find_all_files`,
# however, reading the weights might also have to be abstracted away.


class ProcessorFromOrig(Processor):
    def find_all_files(self):

        self.all_files = self.conf_cmip.find_all_files_orig(**self._files_kwargs)


class ProcessorFromPost(Processor):
    def find_all_files(self):

        self.all_files = self.conf_cmip.find_all_files_post(**self._files_kwargs)
