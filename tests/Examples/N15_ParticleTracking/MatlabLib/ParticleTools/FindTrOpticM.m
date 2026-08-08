function A=FindTrOpticM(PD0,PD,cols)
%find A: PD=(A*PD0(:,cols)')';
 X=PD0(:,cols)'*PD0(:,cols); Y=PD0(:,cols)'*PD(:,cols);  
 A=(inv(X)*Y)'; 
 
 