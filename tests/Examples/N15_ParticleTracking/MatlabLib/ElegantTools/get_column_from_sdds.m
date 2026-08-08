function [column] = get_column_from_sdds(sdds,column_name,npage,L_info)
% function [column]=get_column_from_sdds(sdds,column_name{,npage{,L_info}})
%   Detailed explanation goes here
import SDDS.java.SDDS.*
if nargin==2
    npage=1;
    L_info=false;
elseif nargin==3
    L_info=false;
end
if L_info
    fprintf(1,'%s\n',['file =' char(sdds.filename)]);
    fprintf(1,'%s\n',['descr=' char(sdds.description.text)]);
    fprintf(1,'%s\n',['      ' char(sdds.description.contents)]);
    fprintf(1,'%s\n',['cname=' column_name]);
end
ch=['sdds.column.' column_name '.type'];
% types: 1 for double
%        2     float
%        3     long
%        4     short
%        5     string
%        6     character
eval(['column_type=SDDSUtil.identifyType(' ch ');'])
eval(['cht=char(' ch ');'])
if L_info
    fprintf(1,'%s\n',['ctype=' num2str(column_type)]);
    fprintf(1,'%s\n',['      ' cht]);
end
ch=['sdds.column.' column_name '.page' num2str(npage)];
if column_type==1
    eval(['column=SDDSUtil.castArrayAsDouble(' ch ',column_type);'])
elseif column_type==2
    eval(['column=SDDSUtil.castArrayAsFloat(' ch ',column_type);'])
elseif column_type==3
    eval(['column=SDDSUtil.castArrayAsLong(' ch ',column_type);'])
elseif column_type==4
    column=[];
elseif column_type==5
    eval(['col   =SDDSUtil.castArrayAsString(' ch ',column_type);'])
    column=char(col(:));
else
    column=[];
end
end

