clear all
% read longlist from WD
%[name path] = uigetfile('*.*',  'All Files (*.*)')
proj_name = 'Flash';
path = 'E:\S2E_3rdH\WDecking\';
name = 'component_list_FLASH.txt';
fid = fopen([path name]);
index=0;
while 1
    tline = fgetl(fid);
    if ~ischar(tline), break, end
    if(~strcmp(tline,''))
        index=index+1;
        [longlist(:,index)] = strread(tline,'%s');
    end
end
fclose(fid);
%
%
% write file
%
%[name path] = uiputfile('*.*',  'All Files (*.*)')
fid = fopen([path proj_name '.in'],'w+');
%
%header
header = {
'!----------------------------------------------------------------------------';
'! Alternative XFEL Injector beamline up to end of dogleg, sextupoles off';
'!----------------------------------------------------------------------------';

 '&NEWRUN';
  'Version=2';
  'Head=''Alternative XFEL Injector beamline up to end of dogleg, sextupoles off''';
  'RUN = 1';
  'Loop = .F';
  'Nloop = 1';
  'Distribution = ''d_3rd_chirp_3_1000.ini''';
  'Lmagnetized=.F';
  'EmitS=.T';
  'PhaseS=.T';
  'TrackS=.F';
  'RefS=.T';
  'TcheckS=.F';
  'check_ref_part=.T';
  'High_res=.T';
  'TRACK_ALL=.T';
  'PHASE_SCAN = .F';
  'AUTO_PHASE = .T';
  'ZSTART = 0.1';
  'ZSTOP  = 47.65';
  'Zemit  = 500';
  'Zphase = 20';
  'H_max = 0.005';
  'H_min = 0.001';
'! H_max ist maximale Schrittweitengroesse; sollte auch mit 10x groesser funktionieren';
'!'
 ' MAX_STEP = 5000000';
 ' LSUB_COR = .F';
'  Screen(1)=0.01';
'  Screen(2)=47.41';
' /';
' ';
' &OUTPUT';
' Local_emit = .T';
' /';
' ';
' &SCAN';
' /';
' ';
' &MODULES';
' /';
' ';
' ';
' &ERROR';
' /';
' ';
' &CHARGE';
 'Loop=.T';
 'LSPCH = .F';
'!  Nrad=30';
'!  Nlong_in=300';
 ' Nrad=20';
 ' Nlong_in=100';
 ' Cell_var=2.0';
 ' min_grid=0.0D-6';
 ' Max_scale=0.02';
 ' Lmirror=.F';
 ' N_min=100';
 '/';
 ' ';
' &CSR';
' /';
' ';
' &APERTURE';
' /';
' ';
' &CAVITY';
' /';
' ';
' &SOLENOID';
' /';
 };
%
% write header
for i=1:length(header)
    fprintf(fid,'%s\n', char(header(i)));
end;
%
%
% quads
fprintf(fid,'\n%s\n', '&QUADRUPOLE');
fprintf(fid,'%s\n', 'Loop=.F');
fprintf(fid,'%s\n', 'LQUAD=.T');

index=0;
for i = 1:length(longlist)
    if i==116,
        aa=2;
    end;
    class = char(longlist(5,i));
    if(strcmp(class,'QUAD'));
        index=index+1;
        fprintf(fid,'\n%s\n', ['! Quadrupole ' char(longlist(2,i))]);
        %
        % k is /m in ASTRA, integrated in longlist
        ASTRA_k = str2num(char(longlist(8,i)))/str2num(char(longlist(7,i)));
        fprintf(fid,'%s\n', ['Q_length(' num2str(index) ')=' char(longlist(7,i))]);       
        fprintf(fid,'%s\n', ['Q_K(' num2str(index) ')=' num2str(ASTRA_k)]);
         fprintf(fid,'%s\n', ['Q_Bore(' num2str(index) ')=0.0000001']);
        %
        fprintf(fid,'%s\n', ['Q_pos(' num2str(index) ')=' char(longlist(15,i))]);
      % straight or bent? look at THETA
        if(abs(str2num(char(longlist(16,i)))) > 1e-4);
            fprintf(fid,'%s\n', ['Q_yrot(' num2str(index) ')=' char(longlist(16,i))]);
        end
        if(abs(str2num(char(longlist(14,i)))) > 1e-6);
            fprintf(fid,'%s\n', ['Q_yoff(' num2str(index) ')=' char(longlist(14,i))]);
        end
    end
    if(strcmp(class,'SEXT')); % sextupoles are quads in ASTRA
        index=index+1;
        fprintf(fid,'\n%s\n', ['! Sextupole ' char(longlist(2,i))]);
        fprintf(fid,'%s\n', ['Q_length(' num2str(index) ')=' char(longlist(7,i))]);
        fprintf(fid,'%s\n', ['Q_K(' num2str(index) ')= 0.0001']);
         fprintf(fid,'%s\n', ['Q_Bore(' num2str(index) ')=0.0000001']);
        % scale k2 value
        % k is /m in ASTRA, integrated in longlist
        new_k2 = 0.0 * str2num(char(longlist(8,i)))/0.0001/str2num(char(longlist(7,i)));
        fprintf(fid,'%s\n', ['Q_mult_b(3,' num2str(index) ')= ' num2str(new_k2)]);
        %
        fprintf(fid,'%s\n', ['Q_pos(' num2str(index) ')=' char(longlist(15,i))]);
      % offset or bent? look at YPOS and THETA 
        if(abs(str2num(char(longlist(16,i)))) > 1e-4);
            fprintf(fid,'%s\n', ['Q_yrot(' num2str(index) ')=' char(longlist(16,i))]);
        end
        if(abs(str2num(char(longlist(14,i)))) > 1e-6);
            fprintf(fid,'%s\n', ['Q_yoff(' num2str(index) ')=' char(longlist(14,i))]);
        end
    end
end
fprintf(fid,'%s\n', '/');
% bends
fprintf(fid,'%s\n', '&DIPOLE');
fprintf(fid,'%s\n', 'Loop=.F');
fprintf(fid,'%s\n', 'LDipole=.T');

index=0;
for i=1:length(longlist)
    class = char(longlist(5,i));
    if(strcmp(class,'SBEN'));
        index=index+1;
        fprintf(fid,'\n%s\n', ['! Dipole ' char(longlist(2,i))]);
        %
        % calculate corner points
        %
        % get length and strength
        lbend     = str2num(char(longlist(7,i)));
        phi       = str2num(char(longlist(8,i)));
        %
        rho       = lbend/phi;
        fprintf(fid,'%s\n', ['D_radius (' num2str(index) ')= ' num2str(rho)]);
        %
        ypos      = str2num(char(longlist(14,i)));
        zpos      = str2num(char(longlist(15,i)));
        theta     = str2num(char(longlist(16,i)));
        width     = 0.4;
        %
        e1 = [cos(-theta) sin(-theta)];
        e2 = [cos(-theta + phi/2) sin(-theta + phi/2)];
        e3 = [cos(-theta - phi/2) sin(-theta - phi/2)];
        Midpoint     = [ypos zpos] + rho*e1;
        Entrypoint   = Midpoint - rho*e2;
        Exitpoint    = Midpoint - rho*e3;
        %
        D1           = Midpoint - (rho-width)*e2;
        D2           = Midpoint - (rho+width)*e2;
        D3           = Midpoint - (rho-width)*e3;
        D4           = Midpoint - (rho+width)*e3;
        
        points=[Midpoint; Entrypoint; Exitpoint; D1; D2; D3; D4];
%         if(index==1 || index==4 || index==12 || index==16)
%         figure
%         plot(points(:,2), points(:,1),'o')
%         end


        fprintf(fid,'%s\n', ['D_Type(' num2str(index) ')= ''ver''']);
        fprintf(fid,'%s\n', ['D1(' num2str(index) ')= (' num2str(D1(1)) ',' num2str(D1(2)) ')' ]);
        fprintf(fid,'%s\n', ['D2(' num2str(index) ')= (' num2str(D2(1)) ',' num2str(D2(2)) ')' ]);
        fprintf(fid,'%s\n', ['D3(' num2str(index) ')= (' num2str(D3(1)) ',' num2str(D3(2)) ')' ]);
        fprintf(fid,'%s\n', ['D4(' num2str(index) ')= (' num2str(D4(1)) ',' num2str(D4(2)) ')' ]);
        %
    end
end
fprintf(fid,'%s\n', '/');
%
fclose(fid);

n=length(longlist); T(1:n-2,1:18)=0;
for i=1:18,    T(:,i)=str2num( char( longlist(i+11,3:n) ) )' ; end;
save ([path 'optics.txt'],'T','-ASCII');
