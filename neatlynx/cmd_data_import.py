import sys
import os
from shutil import copyfile
import re
import requests

from neatlynx.cmd_base import CmdBase
from neatlynx.logger import Logger
from neatlynx.data_file_obj import DataFileObj
from neatlynx.exceptions import NeatLynxException
from neatlynx.state_file import StateFile


class DataImportError(NeatLynxException):
    def __init__(self, msg):
        NeatLynxException.__init__(self, 'Import error: {}'.format(msg))


class CmdDataImport(CmdBase):
    def __init__(self):
        CmdBase.__init__(self)
        pass

    def define_args(self, parser):
        self.add_string_arg(parser, 'input', 'Input file')
        self.add_string_arg(parser, 'output', 'Output file')
        pass

    def run(self):
        if not self.git.is_ready_to_go():
            return 1

        if not CmdDataImport.is_url(self.args.input):
            if not os.path.exists(self.args.input):
                raise DataImportError('Input file "{}" does not exist'.format(self.args.input))
            if not os.path.isfile(self.args.input):
                raise DataImportError('Input file "{}" has to be a regular file'.format(self.args.input))

        output = self.args.output
        if os.path.isdir(self.args.output):
            output = os.path.join(output, os.path.basename(self.args.input))

        dobj = DataFileObj(output, self.git, self.config)

        if os.path.exists(dobj.data_file_relative):
            raise DataImportError('Output file "{}" already exists'.format(dobj.data_file_relative))
        if not os.path.isdir(os.path.dirname(dobj.data_file_abs)):
            raise DataImportError('Output file directory "{}" does not exists'.format(
                os.path.dirname(dobj.data_file_relative)))

        os.makedirs(os.path.dirname(dobj.cache_file_relative), exist_ok=True)
        if CmdDataImport.is_url(self.args.input):
            Logger.verbose('Downloading file {} ...'.format(self.args.input))
            self.download_file(self.args.input, dobj.cache_file_relative)
            Logger.verbose('Input file "{}" was downloaded to cache "{}"'.format(
                self.args.input, dobj.cache_file_relative))
        else:
            copyfile(self.args.input, dobj.cache_file_relative)
            Logger.verbose('Input file "{}" was copied to cache "{}"'.format(
                self.args.input, dobj.cache_file_relative))

        cache_relative_to_data = os.path.relpath(dobj.cache_file_relative, os.path.dirname(dobj.data_file_relative))
        os.symlink(cache_relative_to_data, dobj.data_file_relative)
        Logger.verbose('Symlink from data file "{}" to the cache file "{}" was created'.
                       format(dobj.data_file_relative, cache_relative_to_data))

        state_file = StateFile(dobj.state_file_relative, self.git)
        state_file.save()
        Logger.verbose('State file "{}" was created'.format(dobj.state_file_relative))
        pass

    URL_REGEX = re.compile(
        r'^(?:http|ftp)s?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

    @staticmethod
    def is_url(url):
        return CmdDataImport.URL_REGEX.match(url) is not None

    @staticmethod
    def download_file(from_url, to_file):
        r = requests.get(from_url, stream=True)
        with open(to_file, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024*100):
                if chunk:  # filter out keep-alive new chunks
                    f.write(chunk)
        return


if __name__ == '__main__':
    try:
        sys.exit(CmdDataImport().run())
    except NeatLynxException as e:
        Logger.error(e)
        sys.exit(1)
